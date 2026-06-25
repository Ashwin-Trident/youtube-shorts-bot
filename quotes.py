"""
quotes.py
─────────────────────────────────────────────────────────────
Central store for all default quotes used by the YouTube Shorts bot.

Each entry is a dict with these fields:
  {
    "id"        : unique int  (never reuse / reorder),
    "text"      : the quote string,
    "author"    : speaker name,
    "status"    : "pending" | "posted"   ← updated by quote_status.py after upload
    "posted_at" : ISO-8601 UTC string, or None
  }

quote_status.py reads and writes the "status" / "posted_at" fields
directly in this file so everything stays in one place — no separate JSON needed.

To add a new quote: append a new dict with a unique id,
status="pending", and posted_at=None.
─────────────────────────────────────────────────────────────
"""

DEFAULT_QUOTES = [
    {
        "id": 1,
        "text": "I think the reason why I am the person who I am today is because I went through those tough times when I was younger.",
        "author": "LeBron James",
        "status": "posted",
        "posted_at": "2026-06-22T18:45:52",
    },
    {
        "id": 2,
        "text": "Ask me to play. I'll play. Ask me to shoot. I'll shoot. Ask me to pass. I'll pass. Ask me to steal, block out, sacrifice, lead, dominate. Anything. But it's not what you ask of me. It's what I ask of myself.",
        "author": "LeBron James",
        "status": "posted",
        "posted_at": "2026-06-22T22:37:56",
    },
    {
        "id": 3,
        "text": "I always say, decisions I make, I live with them. There's always ways you can correct them or ways you can do them better. At the end of the day, I live with them.",
        "author": "LeBron James",
        "status": "posted",
        "posted_at": "2026-06-23T02:09:12",
    },
    {
        "id": 4,
        "text": "To be successful you have to be selfish, or else you never achieve. And once you get to your highest level, then you have to be unselfish. Stay reachable. Stay in touch. Don't isolate.",
        "author": "Michael Jordan",
        "status": "posted",
        "posted_at": "2026-06-23T06:47:45",
    },
    {
        "id": 5,
        "text": "The basketball court for me, during a game, is the most peaceful place I can imagine. On the basketball court, I worry about nothing. When I'm out there, no one can bother me.",
        "author": "Michael Jordan",
        "status": "posted",
        "posted_at": "2026-06-23T11:58:52",
    },
    {
        "id": 6,
        "text": "Obstacles don't have to stop you. If you run into a wall, don't turn around and give up. Figure out how to climb it, go through it, or work around it.",
        "author": "Michael Jordan",
        "status": "posted",
        "posted_at": "2026-06-23T14:29:15",
    },
    {
        "id": 7,
        "text": "Your love makes me strong, your hate makes me unstoppable.",
        "author": "Cristiano Ronaldo",
        "status": "posted",
        "posted_at": "2026-06-23T17:15:00",
    },
    {
        "id": 8,
        "text": "Talent without working hard is nothing. I'm not perfectionistic, but I like to feel that I have done my best.",
        "author": "Cristiano Ronaldo",
        "status": "posted",
        "posted_at": "2026-06-23T19:53:41",
    },
    {
        "id": 9,
        "text": "Success is no accident. It is hard work, perseverance, learning, studying, sacrifice and most of all, love of what you are doing or learning to do.",
        "author": "Pele",
        "status": "posted",
        "posted_at": "2026-06-23T22:14:36",
    },
    {
        "id": 10,
        "text": "People throw stones at you and you convert them into milestones.",
        "author": "Sachin Tendulkar",
        "status": "posted",
        "posted_at": "2026-06-24T02:09:00",
    },
    {
        "id": 11,
        "text": "I'm a fighter. I believe in the eye-for-an-eye business. I'm no cheek turner. I got no respect for a man who won't hit back. You kill my dog, you better hide your cat.",
        "author": "Muhammad Ali",
        "status": "posted",
        "posted_at": "2026-06-24T06:41:31",
    },
    {
        "id": 12,
        "text": "Don't count the days, make the days count.",
        "author": "Muhammad Ali",
        "status": "posted",
        "posted_at": "2026-06-24T11:43:01",
    },
    {
        "id": 13,
        "text": "The most important thing is to try and inspire people so that they can be great in whatever they want to do.",
        "author": "Kobe Bryant",
        "status": "posted",
        "posted_at": "2026-06-24T14:16:35",
    },
    {
        "id": 14,
        "text": "Everything negative — pressure, challenges — is all an opportunity for me to rise.",
        "author": "Kobe Bryant",
        "status": "posted",
        "posted_at": "2026-06-24T17:04:52",
    },
    {
        "id": 15,
        "text": "I have nothing in common with lazy people who blame others for their lack of success.",
        "author": "Kobe Bryant",
        "status": "posted",
        "posted_at": "2026-06-24T19:31:06",
    },
    {
        "id": 16,
        "text": "I really think a champion is defined not by their wins but by how they can recover when they fall.",
        "author": "Serena Williams",
        "status": "posted",
        "posted_at": "2026-06-24T22:11:32",
    },
    {
        "id": 17,
        "text": "I've had to learn to fight all my life — got to learn to keep smiling. If you smile, things will work out.",
        "author": "Serena Williams",
        "status": "posted",
        "posted_at": "2026-06-25T02:10:54",
    },
    {
        "id": 18,
        "text": "You always want to win. That is why you play tennis, because you love the sport and you try to be the best you can at it.",
        "author": "Roger Federer",
        "status": "posted",
        "posted_at": "2026-06-25T06:45:11",
    },
    {
        "id": 19,
        "text": "I know what I can do, so I never doubt myself.",
        "author": "Usain Bolt",
        "status": "posted",
        "posted_at": "2026-06-25T11:37:07",
    },
    {
        "id": 20,
        "text": "Worrying gets you nowhere. If you turn up worrying about how you're going to perform, you've already lost. Train hard, turn up, run your best, and the rest will take care of itself.",
        "author": "Usain Bolt",
        "status": "posted",
        "posted_at": "2026-06-25T14:07:29",
    },
    {
        "id": 21,
        "text": "No matter how good you get you can always get better, and that's the exciting part.",
        "author": "Tiger Woods",
        "status": "posted",
        "posted_at": "2026-06-25T17:09:17",
    },
    {
        "id": 22,
        "text": "You miss one hundred percent of the shots you don't take.",
        "author": "Wayne Gretzky",
        "status": "pending",
        "posted_at": None,
    },
    {
        "id": 23,
        "text": "Failure happens all the time. It happens every day in practice. What makes you better is how you react to it.",
        "author": "Mia Hamm",
        "status": "pending",
        "posted_at": None,
    },
    {
        "id": 24,
        "text": "We all have dreams. But in order to make dreams come into reality, it takes an awful lot of determination, dedication, self-discipline, and effort.",
        "author": "Jesse Owens",
        "status": "pending",
        "posted_at": None,
    },
    {
        "id": 25,
        "text": "Champions keep playing until they get it right.",
        "author": "Billie Jean King",
        "status": "pending",
        "posted_at": None,
    },
]
