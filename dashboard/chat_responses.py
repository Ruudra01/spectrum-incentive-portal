"""Canned policy answers for the demo assistant. No LLM call.

Every figure is interpolated from mock_data, so an answer can never
contradict what the dashboard is showing.
"""

from . import mock_data

_BY_SLUG = {tier["slug"]: tier for tier in mock_data.TIERS}
_SILVER_MIN = _BY_SLUG["silver"]["min_points"]
_GOLD_MIN = _BY_SLUG["gold"]["min_points"]
_BRONZE_MAX = _BY_SLUG["bronze"]["max_points"]
_BOARD_SIZE = len(mock_data.LEADERBOARD)
_WEEKS = len(mock_data.WEEKLY_POINTS)
_GOLD_PERKS = _BY_SLUG["gold"]["perks"]

FAQ_RESPONSES = [
    {
        "keywords": ["points calculated", "how are points", "earn points", "how do i earn", "calculate"],
        "question": "How are my points calculated?",
        "answer": (
            f"Points come from three sources: completed installs, qualified upsells, "
            f"and your rolling CSAT score. Each job posts to your balance once it clears "
            f"quality review, usually within 48 hours. Your dashboard shows the last "
            f"{_WEEKS} weeks so you can see how the total is trending."
        ),
    },
    {
        "keywords": ["payout", "paid", "payment", "when do i get", "cash out"],
        "question": "When do payouts happen?",
        "answer": (
            "Payouts run on the first business day of each month and cover everything "
            "posted through the last day of the prior month. Your tier multiplier is "
            "locked in at the moment of payout, not when the job closed. Anything still "
            "in quality review rolls to the following cycle."
        ),
    },
    {
        "keywords": ["gold", "top tier", "highest tier"],
        "question": f"What does it take to reach Gold?",
        "answer": (
            f"Gold starts at {_GOLD_MIN:,} points. Silver runs from {_SILVER_MIN:,} to "
            f"{_GOLD_MIN - 1:,}, so the climb from the bottom of Silver is "
            f"{_GOLD_MIN - _SILVER_MIN:,} points. Gold unlocks {_GOLD_PERKS[0].lower()}, "
            f"{_GOLD_PERKS[1].lower()}, and {_GOLD_PERKS[2].lower()}."
        ),
    },
    {
        "keywords": ["expire", "expiry", "reset", "roll over", "lose my points"],
        "question": "Do my points expire?",
        "answer": (
            "Points do not expire during the program year. Your balance carries forward "
            "month to month and only resets at the annual program rollover. Tier standing "
            "is recalculated from your live balance, so it never drops because of the calendar."
        ),
    },
    {
        "keywords": ["leaderboard", "rank", "ranking", "standing", "where do i stand"],
        "question": "How is the leaderboard ranked?",
        "answer": (
            f"The board ranks the top {_BOARD_SIZE} agents by total points, highest first. "
            "Ties break on the most recent qualifying job. It refreshes whenever a job "
            "clears review, so your position can move without any action from you."
        ),
    },
    {
        "keywords": ["upsell", "qualified", "qualifies", "what counts"],
        "question": "What counts as a qualified upsell?",
        "answer": (
            "An upsell qualifies when the customer keeps the added service past the "
            "30-day cancellation window. Downgrades inside that window claw the points "
            "back automatically. Bundled add-ons sold at the time of install count as a "
            "single upsell, not one per line item."
        ),
    },
]

FALLBACK_RESPONSE = (
    "I only cover incentive program policy, so I may have missed that one. Try asking "
    f"how points are calculated, what it takes to reach Gold at {_GOLD_MIN:,} points, "
    "or when payouts happen."
)


def match_question(text):
    """Return the answer whose keywords first appear in the text, else the fallback."""
    haystack = (text or "").lower()
    for entry in FAQ_RESPONSES:
        if any(keyword in haystack for keyword in entry["keywords"]):
            return entry["answer"]
    return FALLBACK_RESPONSE


if __name__ == "__main__":
    assert len(FAQ_RESPONSES) == 6
    # Every pill must route back to its own answer.
    for item in FAQ_RESPONSES:
        assert match_question(item["question"]) == item["answer"], item["question"]
    # Typed phrasings, not just the pill text.
    assert match_question("do my points expire?") == FAQ_RESPONSES[3]["answer"]
    assert match_question("WHEN DO I GET PAID") == FAQ_RESPONSES[1]["answer"]
    assert match_question("hi there") == FALLBACK_RESPONSE
    assert match_question("") == FALLBACK_RESPONSE
    assert match_question(None) == FALLBACK_RESPONSE
    # No answer may state a threshold the dashboard disagrees with.
    assert str(_GOLD_MIN) in FAQ_RESPONSES[2]["answer"].replace(",", "")
    assert _BRONZE_MAX == _SILVER_MIN - 1
    print("chat_responses OK")
