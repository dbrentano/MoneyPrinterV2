import re
import sys
import time
import os
import json

from cache import *
from config import *
from status import *
from llm_provider import generate_text
from typing import List, Optional
from datetime import datetime
from termcolor import colored
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class Twitter:
    """
    Class for the Bot, that grows a Twitter account.
    """

    def __init__(
        self, account_uuid: str, account_nickname: str, fp_profile_path: str, topic: str
    ) -> None:
        """
        Initializes the Twitter Bot.

        Args:
            account_uuid (str): The account UUID
            account_nickname (str): The account nickname
            fp_profile_path (str): The path to the Firefox profile

        Returns:
            None
        """
        self.account_uuid: str = account_uuid
        self.account_nickname: str = account_nickname
        self.fp_profile_path: str = fp_profile_path
        self.topic: str = topic

        # Initialize the Firefox profile
        self.options: Options = Options()

        # Set headless state of browser
        if get_headless():
            self.options.add_argument("--headless")

        if not os.path.isdir(fp_profile_path):
            raise ValueError(
                f"Firefox profile path does not exist or is not a directory: {fp_profile_path}"
            )

        # Set the profile path
        self.options.add_argument("-profile")
        self.options.add_argument(fp_profile_path)

        # Set the service
        self.service: Service = Service(GeckoDriverManager().install())

        # Initialize the browser
        self.browser: webdriver.Firefox = webdriver.Firefox(
            service=self.service, options=self.options
        )
        self.wait: WebDriverWait = WebDriverWait(self.browser, 30)

    def post(self, text: Optional[str] = None) -> None:
        """
        Starts the Twitter Bot.

        Args:
            text (str): The text to post

        Returns:
            None
        """
        bot: webdriver.Firefox = self.browser
        verbose: bool = get_verbose()

        bot.get("https://x.com/compose/post")

        post_content: str = text if text is not None else self.generate_post()
        now: datetime = datetime.now()

        print(colored(" => Posting to Twitter:", "blue"), post_content[:30] + "...")
        body = post_content

        text_box = None
        text_box_selectors = [
            (By.CSS_SELECTOR, "div[data-testid='tweetTextarea_0'][role='textbox']"),
            (By.XPATH, "//div[@data-testid='tweetTextarea_0']//div[@role='textbox']"),
            (By.CSS_SELECTOR, "div[role='textbox'][contenteditable='true']"),
            (By.XPATH, "//div[@role='textbox']"),
        ]

        for selector in text_box_selectors:
            try:
                text_box = self.wait.until(EC.element_to_be_clickable(selector))
                bot.execute_script("arguments[0].scrollIntoView({block: 'center'});", text_box)
                text_box.click()
                ActionChains(bot).move_to_element(text_box).click().send_keys(body).perform()

                entered_text = (
                    text_box.text
                    or text_box.get_attribute("textContent")
                    or text_box.get_attribute("innerText")
                    or ""
                )
                if body[:20] in entered_text:
                    break
                break
            except Exception:
                continue

        if text_box is None:
            raise RuntimeError(
                "Could not find tweet text box. Ensure you are logged into X in this Firefox profile."
            )

        post_button = None
        post_button_selectors = [
            (By.XPATH, "//button[@data-testid='tweetButtonInline']"),
            (By.XPATH, "//button[@data-testid='tweetButton']"),
            (By.XPATH, "//span[text()='Post']/ancestor::button"),
            (By.XPATH, "//span[text()='Post']/ancestor::*[@role='button']"),
        ]

        for selector in post_button_selectors:
            try:
                candidate = self.wait.until(EC.presence_of_element_located(selector))
                if not candidate.is_enabled():
                    continue

                post_button = candidate
                bot.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    post_button,
                )

                try:
                    self.wait.until(lambda _: post_button.is_enabled())
                    post_button.click()
                except Exception:
                    bot.execute_script("arguments[0].click();", post_button)
                break
            except Exception:
                continue

        if post_button is None:
            raise RuntimeError("Could not find the Post button on X compose screen.")

        time.sleep(2)

        compose_visible = any(
            bot.find_elements(*selector) for selector in text_box_selectors
        )
        if compose_visible:
            if verbose:
                warning("Post button click may not have submitted. Trying Ctrl+Enter.")
            ActionChains(bot).key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()

        if verbose:
            print(colored(" => Pressed [ENTER] Button on Twitter..", "blue"))
        time.sleep(2)

        # Add the post to the cache
        self.add_post({"content": body, "date": now.strftime("%m/%d/%Y, %H:%M:%S")})

        success("Posted to Twitter successfully!")

    def get_posts(self) -> List[dict]:
        """
        Gets the posts from the cache.

        Returns:
            posts (List[dict]): The posts
        """
        if not os.path.exists(get_twitter_cache_path()):
            # Create the cache file
            with open(get_twitter_cache_path(), "w") as file:
                json.dump({"accounts": []}, file, indent=4)

        with open(get_twitter_cache_path(), "r") as file:
            parsed = json.load(file)

            # Find our account
            accounts = parsed["accounts"]
            for account in accounts:
                if account["id"] == self.account_uuid:
                    posts = account["posts"]

                    if posts is None:
                        return []

                    # Return the posts
                    return posts

        return []

    def add_post(self, post: dict) -> None:
        """
        Adds a post to the cache.

        Args:
            post (dict): The post to add

        Returns:
            None
        """
        posts = self.get_posts()
        posts.append(post)

        with open(get_twitter_cache_path(), "r") as file:
            previous_json = json.loads(file.read())

            # Find our account
            accounts = previous_json["accounts"]
            for account in accounts:
                if account["id"] == self.account_uuid:
                    account["posts"].append(post)

            # Commit changes
            with open(get_twitter_cache_path(), "w") as f:
                f.write(json.dumps(previous_json))

    def _clean_generated_post(self, text: str) -> str:
        """
        Cleans model output to remove prompt leakage and chat-template artifacts.

        Args:
            text (str): Raw model output

        Returns:
            cleaned (str): Cleaned tweet text
        """
        cleaned = str(text or "")
        cleaned = re.sub(r"<\|.*?\|>", " ", cleaned)
        cleaned = re.sub(r"m_start\|>", " ", cleaned)
        cleaned = re.sub(r"</?[^>]+>", " ", cleaned)
        cleaned = cleaned.replace('"', "").replace("*", "")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _is_valid_generated_post(self, text: str) -> bool:
        """
        Validates a generated tweet before posting.

        Args:
            text (str): Candidate tweet

        Returns:
            is_valid (bool): Whether the tweet is acceptable
        """
        if not text:
            return False

        lowered = text.lower()
        blocked_fragments = [
            "generate a twitter post about",
            "return only the tweet text",
            "do not include",
            "topic:",
            "rules:",
            "assistant",
            "user",
            "system",
            "im_start",
            "im_end",
        ]

        if any(fragment in lowered for fragment in blocked_fragments):
            return False

        if any(ord(char) > 127 for char in text):
            return False

        return len(text) <= 260

    def generate_post(self) -> str:
        """
        Generates a post for the Twitter account based on the topic.

        Returns:
            post (str): The post
        """
        if get_verbose():
            info("Generating a post...")

        prompt = (
            f"Write one short tweet in natural {get_twitter_language()} about this topic: {self.topic}.\n\n"
            "Rules:\n"
            "- Return only the tweet text.\n"
            "- Do not include explanations, labels, markdown, XML tags, or prompt text.\n"
            "- Do not mention these instructions.\n"
            "- Use English only.\n"
            "- Maximum 220 characters.\n"
            "- Maximum 2 sentences.\n"
            "- Sound like a normal human tweet, not an AI assistant.\n"
            "- Focus on one specific angle of the topic.\n"
        )

        for attempt in range(1, 4):
            completion = generate_text(prompt)
            cleaned = self._clean_generated_post(completion)

            if self._is_valid_generated_post(cleaned):
                if get_verbose():
                    info(f"Length of post: {len(cleaned)}")
                return cleaned

            if get_verbose():
                warning(f"Generated post was invalid on attempt {attempt}. Retrying...")

        error("Failed to generate a clean Twitter post after multiple attempts.")
        sys.exit(1)
