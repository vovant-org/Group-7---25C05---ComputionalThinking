"""AI integration (free tier only): read the user's input, then draw a picture of exactly that content.

    reader.py  an LLM reads the topic / reference text and returns scenes: a claim (taken from the user's text)
               plus an English description of a picture that shows THAT claim
    llm.py     free text providers (Pollinations without a key, Gemini with a free AI Studio key)
    images.py  free image providers (Pollinations; a folder of pictures made by hand in Google Flow / ImageFX)
               + disk cache, rate limit and a fallback that never stops the video

Everything here is optional. If a provider fails, make_video falls back to the drawn-by-code infographic.
Text and numbers on screen are still drawn by code from the claim (criterion S15), never by an image model.
"""
