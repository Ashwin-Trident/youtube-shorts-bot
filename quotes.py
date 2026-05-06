"""
quotes.py
─────────────────────────────────────────────────────────────
Central store for all default quotes used by the YouTube Shorts bot.

Each entry is a dict:
  {
    "id"     : unique int  (never reuse / reorder),
    "text"   : the quote string,
    "author" : speaker name,
  }

Status (posted / pending) is tracked separately in quotes_status.json
so this file stays clean and version-control friendly.

To add more quotes: append to DEFAULT_QUOTES with a new unique id.
"""

DEFAULT_QUOTES = [
    # ── LeBron James ──────────────────────────────────────────────────────
    {
        "id": 1,
        "text": (
            "I think the reason why I am the person who I am today is because "
            "I went through those tough times when I was younger."
        ),
        "author": "LeBron James",
    },
    {
        "id": 2,
        "text": (
            "Ask me to play. I'll play. Ask me to shoot. I'll shoot. "
            "Ask me to pass. I'll pass. Ask me to steal, block out, sacrifice, "
            "lead, dominate. Anything. But it's not what you ask of me. "
            "It's what I ask of myself."
        ),
        "author": "LeBron James",
    },
    {
        "id": 3,
        "text": (
            "I always say, decisions I make, I live with them. There's always "
            "ways you can correct them or ways you can do them better. "
            "At the end of the day, I live with them."
        ),
        "author": "LeBron James",
    },
    # ── Michael Jordan ────────────────────────────────────────────────────
    {
        "id": 4,
        "text": (
            "To be successful you have to be selfish, or else you never achieve. "
            "And once you get to your highest level, then you have to be unselfish. "
            "Stay reachable. Stay in touch. Don't isolate."
        ),
        "author": "Michael Jordan",
    },
    {
        "id": 5,
        "text": (
            "The basketball court for me, during a game, is the most peaceful "
            "place I can imagine. On the basketball court, I worry about nothing. "
            "When I'm out there, no one can bother me."
        ),
        "author": "Michael Jordan",
    },
    {
        "id": 6,
        "text": (
            "Obstacles don't have to stop you. If you run into a wall, don't turn "
            "around and give up. Figure out how to climb it, go through it, "
            "or work around it."
        ),
        "author": "Michael Jordan",
    },
    # ── Cristiano Ronaldo ─────────────────────────────────────────────────
    {
        "id": 7,
        "text": "Your love makes me strong, your hate makes me unstoppable.",
        "author": "Cristiano Ronaldo",
    },
    {
        "id": 8,
        "text": (
            "Talent without working hard is nothing. I'm not perfectionistic, "
            "but I like to feel that I have done my best."
        ),
        "author": "Cristiano Ronaldo",
    },
    # ── Pelé ──────────────────────────────────────────────────────────────
    {
        "id": 9,
        "text": (
            "Success is no accident. It is hard work, perseverance, learning, "
            "studying, sacrifice and most of all, love of what you are doing "
            "or learning to do."
        ),
        "author": "Pele",
    },
    # ── Sachin Tendulkar ──────────────────────────────────────────────────
    {
        "id": 10,
        "text": "People throw stones at you and you convert them into milestones.",
        "author": "Sachin Tendulkar",
    },
    # ── Muhammad Ali ──────────────────────────────────────────────────────
    {
        "id": 11,
        "text": (
            "I'm a fighter. I believe in the eye-for-an-eye business. "
            "I'm no cheek turner. I got no respect for a man who won't hit back. "
            "You kill my dog, you better hide your cat."
        ),
        "author": "Muhammad Ali",
    },
    {
        "id": 12,
        "text": (
            "Don't count the days, make the days count."
        ),
        "author": "Muhammad Ali",
    },
    # ── Kobe Bryant ───────────────────────────────────────────────────────
    {
        "id": 13,
        "text": (
            "The most important thing is to try and inspire people so that "
            "they can be great in whatever they want to do."
        ),
        "author": "Kobe Bryant",
    },
    {
        "id": 14,
        "text": (
            "Everything negative — pressure, challenges — is all an opportunity "
            "for me to rise."
        ),
        "author": "Kobe Bryant",
    },
    {
        "id": 15,
        "text": (
            "I have nothing in common with lazy people who blame others for "
            "their lack of success."
        ),
        "author": "Kobe Bryant",
    },
    # ── Serena Williams ───────────────────────────────────────────────────
    {
        "id": 16,
        "text": (
            "I really think a champion is defined not by their wins but by how "
            "they can recover when they fall."
        ),
        "author": "Serena Williams",
    },
    {
        "id": 17,
        "text": (
            "I've had to learn to fight all my life — got to learn to keep "
            "smiling. If you smile, things will work out."
        ),
        "author": "Serena Williams",
    },
    # ── Roger Federer ─────────────────────────────────────────────────────
    {
        "id": 18,
        "text": (
            "You always want to win. That is why you play tennis, because you "
            "love the sport and you try to be the best you can at it."
        ),
        "author": "Roger Federer",
    },
    # ── Usain Bolt ────────────────────────────────────────────────────────
    {
        "id": 19,
        "text": (
            "I know what I can do, so I never doubt myself."
        ),
        "author": "Usain Bolt",
    },
    {
        "id": 20,
        "text": (
            "Worrying gets you nowhere. If you turn up worrying about how you're "
            "going to perform, you've already lost. Train hard, turn up, run "
            "your best, and the rest will take care of itself."
        ),
        "author": "Usain Bolt",
    },
    # ── Tiger Woods ───────────────────────────────────────────────────────
    {
        "id": 21,
        "text": (
            "No matter how good you get you can always get better, and that's "
            "the exciting part."
        ),
        "author": "Tiger Woods",
    },
    # ── Wayne Gretzky ─────────────────────────────────────────────────────
    {
        "id": 22,
        "text": "You miss one hundred percent of the shots you don't take.",
        "author": "Wayne Gretzky",
    },
    # ── Mia Hamm ─────────────────────────────────────────────────────────
    {
        "id": 23,
        "text": (
            "Failure happens all the time. It happens every day in practice. "
            "What makes you better is how you react to it."
        ),
        "author": "Mia Hamm",
    },
    # ── Jesse Owens ───────────────────────────────────────────────────────
    {
        "id": 24,
        "text": (
            "We all have dreams. But in order to make dreams come into reality, "
            "it takes an awful lot of determination, dedication, self-discipline, "
            "and effort."
        ),
        "author": "Jesse Owens",
    },
    # ── Billie Jean King ─────────────────────────────────────────────────
    {
        "id": 25,
        "text": (
            "Champions keep playing until they get it right."
        ),
        "author": "Billie Jean King",
    },
]
