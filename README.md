# Aswamedham AI (Guess the Person) Bot

A Telegram bot inspired by the popular quiz show *Aswamedham* hosted by Grandmaster G.S. Pradeep on the Malayalam TV channel Kairali. The bot is powered by the Qwen 3:4b large language model (via Ollama), and allows users to guess a famous personality through yes/no questions.

---

## About the Game

Aswamedham is a quiz game where one participant thinks of a famous personality, and the others try to guess who it is by asking yes/no questions. It gained widespread recognition in Kerala through the TV show hosted by Grandmaster G.S. Pradeep. This bot brings the same excitement to Telegram using an AI that answers your questions.

---

## Features

- A.I picks a from a list of a famous personalities (easily extendable).
- Ask up to 10 yes/no questions to AI.
- Up to 3 guesses per game.
- A summary option to see the thinking process of AI.
- Works in group chats (shared session) and private chats (per-user sessions).
- No need to match accents or exact spellings – smart name normalization is supported.

---

## Local Setup (Tested on Linux and macOS)

### 1. Prerequisites

- Python 3.8 or higher
- Git

### 2. Quick Setup Instructions

```bash
# Clone the repository
git clone https://github.com/sneerajmohan/aswamedham_ai.git
cd aswamedham_ai

# Install Python dependencies
pip3 install -r requirements.txt

# Install Ollama (Linux/macOS)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the Qwen 3:4b model
ollama pull qwen:3.4b
```

### 3. Configuration

export your bot token:

```bash
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
```

### 4. Run the Bot

```bash
python3 aswamedham_bot.py
```

The bot will now be accessible via Telegram and ready to play!

---

## Commands

| Command       | Description |
|---------------|-------------|
| /start        | Start a new game |
| /ask <question> | Ask a yes/no question |
| /guess <name> | Guess the person |
| /namelist     | View the 100-person shortlist |
| /next         | Next page of names |
| /history      | View Q&A and guesses so far |
| /scorecard    | Show remaining questions & guesses |
| /summary      | View the final game log |
| /end          | End the current game |
| /help         | Show help message |

---

## Data

- The list of people is stored in `people.txt`. Currently includes ~152 popular names.
- At the start of each game, 100 names are randomly selected for that session.

You can easily add more names to the list. Duplicates are removed automatically.

---

## Limitations and Notes

- Qwen 3:4b runs smoothly on machines with **16 GB RAM** or higher (CPU inference).
- Currently supports up to 3 concurrent users. For heavier usage, consider scaling infrastructure beyond Ollama.
- Heavily used chatgpt and deepseek to write the code for this bot.


## Collaborations

>  Interested in deploying this at scale or contributing? Feel free to reach out!

---

## License

This project is licensed under the MIT License.

    Note: The Qwen 3:4b language model used in this project is provided by Alibaba Cloud and governed by its own Qianwen License 1.0. This repository does not include the model itself — only the interface code to run it via Ollama.

The interface and bot code in this repository is © 2025 Neeraj Mohan Sushma and released under the MIT License for research and personal use.