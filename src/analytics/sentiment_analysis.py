"""
Sentiment Analysis Module - TextBlob with VADER fallback
"""
import nltk
from src.config.logger import logger

_TEXTBLOB_AVAILABLE = False
_VADER_AVAILABLE = False

try:
    from textblob import TextBlob
    _TEXTBLOB_AVAILABLE = True
except ImportError:
    logger.warning("TextBlob not installed; using VADER fallback if available")

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _VADER_AVAILABLE = True
except ImportError:
    logger.warning("vaderSentiment not installed")


def _ensure_nltk_data():
    for resource in ("punkt", "punkt_tab"):
        try:
            nltk.data.find(f"tokenizers/{resource}")
        except LookupError:
            try:
                nltk.download(resource, quiet=True)
            except Exception as exc:
                logger.debug(f"Could not download NLTK resource {resource}: {exc}")


_ensure_nltk_data()


class SentimentAnalyzer:
    """Analyzes sentiment of reviews with graceful fallbacks."""

    def __init__(self):
        self.positive_threshold = 0.1
        self.negative_threshold = -0.1
        self._vader = SentimentIntensityAnalyzer() if _VADER_AVAILABLE else None

    def analyze_sentiment(self, text):
        """Return sentiment label, polarity, and subjectivity."""
        text = str(text or "").strip()
        if not text:
            return {"sentiment": "Neutral", "polarity": 0.0, "subjectivity": 0.0}

        if _TEXTBLOB_AVAILABLE:
            try:
                blob = TextBlob(text)
                polarity = blob.sentiment.polarity
                subjectivity = blob.sentiment.subjectivity
                return {
                    "sentiment": self._classify_sentiment(polarity),
                    "polarity": round(polarity, 3),
                    "subjectivity": round(subjectivity, 3),
                }
            except Exception as exc:
                logger.debug(f"TextBlob failed, falling back to VADER: {exc}")

        if self._vader:
            try:
                scores = self._vader.polarity_scores(text)
                polarity = scores["compound"]
                return {
                    "sentiment": self._classify_sentiment(polarity),
                    "polarity": round(polarity, 3),
                    "subjectivity": round(abs(polarity), 3),
                }
            except Exception as exc:
                logger.debug(f"VADER failed: {exc}")

        return {"sentiment": "Neutral", "polarity": 0.0, "subjectivity": 0.0}

    def _classify_sentiment(self, polarity):
        if polarity > self.positive_threshold:
            return "Positive"
        if polarity < self.negative_threshold:
            return "Negative"
        return "Neutral"

    def batch_analyze(self, texts):
        return [self.analyze_sentiment(text) for text in texts]

    def get_sentiment_distribution(self, texts):
        sentiments = {"Positive": 0, "Negative": 0, "Neutral": 0}
        for text in texts:
            result = self.analyze_sentiment(text)
            sentiments[result["sentiment"]] += 1

        total = sum(sentiments.values())
        percentages = (
            {k: round((v / total) * 100, 2) for k, v in sentiments.items()}
            if total
            else sentiments.copy()
        )
        return {"counts": sentiments, "percentages": percentages, "total": total}
