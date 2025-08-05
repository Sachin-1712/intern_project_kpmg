
import json
from master_router import MasterRouter

bot = MasterRouter()
uid = "cli"  

print("Assistant ready. Type 'exit' to quit.")
while True:
    text = input("> ").strip()
    if text.lower() in {"exit", "quit"}:
        break

    if text.lower() == "show memory":
        print(" Memory:", json.dumps(bot.memory, indent=2))
        continue

    if text.lower() == "show pending":
        print(" Pending:", json.dumps(bot.pending, indent=2))
        continue

    if not text:
        continue

    reply = bot.process(uid, text)
    print(reply)
