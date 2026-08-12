import asyncio
import random
from telethon import TelegramClient
from telethon.tl.functions.messages import SetTypingRequest
from telethon.tl.types import SendMessageTypingAction

class Humanizer:
    @staticmethod
    async def wait_before_acting(user_message: str = ""):
        """Simulates natural human reading time based on the customer's message length."""
        # Base delay + time it takes to read their specific message (approx 300ms per word)
        word_count = len(user_message.split())
        read_time = word_count * 0.3  
        delay = min(random.uniform(1.5, 3.5) + read_time, 10.0) # Caps at 10 seconds so the bot doesn't freeze
        
        print(f"[Humanizer] Reading message ({word_count} words). Waiting {delay:.2f}s...")
        await asyncio.sleep(delay)

    @staticmethod
    async def simulate_typing(client: TelegramClient, entity, duration: float, action_type: str = "text"):
        """Shows typing indicator with natural 'thinking' pauses."""
        action = SendMessageTypingAction()
        time_remaining = duration
        
        while time_remaining > 0:
            try:
                await client(SetTypingRequest(peer=entity, action=action))
            except Exception as e:
                print(f"[Humanizer] Typing action error: {e}")
            
            # 30% chance to simulate the human stopping typing to think about what to say next
            if time_remaining > 3.0 and random.random() < 0.3:
                pause_duration = random.uniform(1.5, 3.0)
                await asyncio.sleep(pause_duration)
                time_remaining -= pause_duration
            
            sleep_chunk = min(random.uniform(2.0, 4.0), time_remaining)
            await asyncio.sleep(sleep_chunk)
            time_remaining -= sleep_chunk

    @staticmethod
    def inject_human_typos(text: str) -> str:
        """Introduces a minor typo or casual text formatting to simulate fast mobile typing."""
        # 1. 25% chance to drop trailing punctuation to mimic casual texting
        if text.endswith(('.', '!')) and random.random() < 0.25:
            text = text[:-1]
            
        # 2. 10% chance of a slight 'fat-finger' keyboard slip
        if random.random() > 0.10:
            return text
            
        typo_map = {'a': 's', 's': 'd', 'e': 'r', 'o': 'p', 'i': 'u', 'n': 'b', 'm': 'n'}
        words = text.split()
        
        if len(words) > 3:
            # Pick a random word in the middle of the sentence so it's subtle
            idx = random.randint(1, len(words) - 2)
            word = list(words[idx])
            for i in range(len(word)):
                if word[i].lower() in typo_map and random.random() > 0.5:
                    word[i] = typo_map[word[i].lower()]
                    break
            words[idx] = "".join(word)
            
        return " ".join(words)