from config import POE_TOKEN

class PoeProvider:
    def ask(self, prompt: str, bot: str = "gemini-2.0-flash") -> str:
        # Skip if no token yet
        if not POE_TOKEN:
            raise Exception("POE_TOKEN not set")
        try:
            from poe_api_wrapper import PoeApi
            client = PoeApi(POE_TOKEN)
            response = ""
            for chunk in client.send_message(bot, prompt):
                response = chunk["response"]
            return response
        except Exception as e:
            raise Exception(f"Poe failed: {e}")
