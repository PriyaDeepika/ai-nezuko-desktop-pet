# 🌸 AI Nezuko Desktop Pet

An AI-powered desktop companion featuring Nezuko (Demon Slayer) — she walks around your screen, reacts with animations, and chats with you in character using the Gemini API.

## Features
- Wanders your desktop with idle, walking, and bounce animations
- Drag her around — she reacts!
- Click her to open a chat window and talk to her
- Responds in Nezuko's personality using Gemini API

## Current Limitations
This is a basic first version. Right now:
- Animations are mapped to emotions in a simple way (limited by available sprite sets)
- No memory — she doesn't remember past conversations after closing
- Expressions are limited to existing Shimeji animations

## Future Improvements
- Add memory so she remembers past conversations
- Generate custom sprites for more expressions (happy, sad, surprised faces)
- More natural, varied behaviors and reactions
- Voice interaction

## Setup
1. Clone this repo
2. `pip install pillow requests`
3. Copy `config_example.py` to `config.py` and add your Gemini API key
4. Run `python main.py`

## Built With
- Python, Tkinter, Pillow
- Google Gemini API
