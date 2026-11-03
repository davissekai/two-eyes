"""Sharing: a WhatsApp preview of exactly what gets sent, the share link, and what to do next."""
import html

from . import card
from .case_file import data_uri


def preview_html(share_text, card_png):
    """A WhatsApp-style bubble with the real card thumbnail and the message, so nobody sends blind."""
    thumb = ""
    if card_png:
        thumb = f'<img class="thumb" src="{data_uri(card_png, max_side=360)}" alt="Your evidence card">'
    return (
        '<div class="chat" aria-label="Preview of the WhatsApp message">'
        '<div class="chat-top"><i></i>Your group</div>'
        f'<div class="bubble">{thumb}<p>{html.escape(share_text or "")}</p>'
        '<div class="ts">✓✓</div></div></div>')


def buttons_html(share_text):
    """One-tap WhatsApp share. Saving the card is a real download button next to it (in app.py)."""
    if not share_text:
        return ""
    return (f'<a class="wa" href="{html.escape(card.whatsapp_url(share_text))}" target="_blank" '
            'rel="noopener">Share on WhatsApp</a>'
            '<p class="hint">The card has no name, phone number or exact location on it.</p>')


def next_steps_html():
    """Where the evidence can go after it is shared."""
    steps = [
        ("Report it to the Minerals Commission",
         "They can say whether this site has a mining licence. Attach the card."),
        ("Send it to a journalist or a local NGO",
         "Groups that track galamsey can follow it up and protect your name."),
        ("Check another spot on the same river",
         "Two spots on one river narrow down where the mud comes from."),
    ]
    items = "".join(f"<li><b>{t}</b><small>{d}</small></li>" for t, d in steps)
    return f'<div class="next-steps"><div class="label">What next?</div><ul>{items}</ul></div>'
