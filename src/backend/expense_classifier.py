"""
Simple Expense Category Classifier using TF-IDF + Logistic Regression

This module provides a simple NLP model to automatically categorize expenses
based on their text description.
"""

import pickle
import os
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
import pandas as pd


class ExpenseClassifier:
    """
    Simple expense category classifier using TF-IDF + Logistic Regression
    """

    def __init__(
        self,
        model_path: str = "expense_model.pkl",
        training_data_path: str = "training_data.json",
    ):
        """
        Initialize the classifier

        Args:
            model_path: Path to save/load the trained model
            training_data_path: Path to the JSON file containing training data
        """
        self.model_path = model_path
        self.training_data_path = training_data_path
        self.model = None
        self.categories = [
            "Food & Dining",
            "Transport",
            "Entertainment",
            "Shopping",
            "Utilities",
            "Healthcare",
            "Education",
            "Other",
        ]

        # Try to load existing model, otherwise create new one
        if os.path.exists(model_path):
            self.load_model()
        else:
            self._create_default_model()

    def _create_default_model(self):
        """Create a new model with training data from JSON file"""

        # Load training data from JSON file
        try:
            with open(self.training_data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                training_entries = data["training_data"]
        except FileNotFoundError:
            print(f"Warning: Training data file '{self.training_data_path}' not found.")
            print("Using minimal fallback training data.")
            # Minimal fallback data
            training_entries = [
                {"description": "Restaurant meal", "category": "Food & Dining"},
                {"description": "Taxi ride", "category": "Transport"},
                {"description": "Movie tickets", "category": "Entertainment"},
                {"description": "New clothes", "category": "Shopping"},
                {"description": "Electricity bill", "category": "Utilities"},
                {"description": "Doctor visit", "category": "Healthcare"},
                {"description": "Online course", "category": "Education"},
                {"description": "Miscellaneous", "category": "Other"},
            ]
        except Exception as e:
            print(f"Error loading training data: {e}")
            return

        # Extract descriptions and categories
        descriptions = [entry["description"] for entry in training_entries]
        categories = [entry["category"] for entry in training_entries]

        # Create a simple TF-IDF + Logistic Regression pipeline
        self.model = Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        lowercase=True, stop_words="english", max_features=200
                    ),
                ),
                (
                    "classifier",
                    LogisticRegression(max_iter=200, random_state=42),
                ),
            ]
        )

        # Train the model
        self.model.fit(descriptions, categories)

        # Save the trained model
        self.save_model()

    def predict(self, description: str) -> dict:
        """
        Predict the category for a given description

        Args:
            description: Text description of the expense (e.g., "Uber ride to office")

        Returns:
            Dictionary with 'category' (predicted category) and 'confidence' (prediction probability)
        """
        if not self.model:
            return {"category": "Other", "confidence": 0.0}

        # Get prediction
        predicted_category = self.model.predict([description])[0]

        # Get prediction probabilities
        probabilities = self.model.predict_proba([description])[0]
        confidence = float(max(probabilities))

        return {"category": predicted_category, "confidence": round(confidence, 3)}

    def save_model(self):
        """Save the trained model to disk"""
        try:
            with open(self.model_path, "wb") as f:
                pickle.dump(self.model, f)
        except Exception as e:
            print(f"Error saving model: {e}")

    def load_model(self):
        """Load a pre-trained model from disk"""
        try:
            with open(self.model_path, "rb") as f:
                self.model = pickle.load(f)
        except Exception as e:
            print(f"Error loading model: {e}")
            self._create_default_model()

    def retrain(self, descriptions: list, categories: list):
        """
        Retrain the model with new data

        Args:
            descriptions: List of text descriptions
            categories: List of corresponding categories
        """
        if len(descriptions) != len(categories):
            print("Error: descriptions and categories must have the same length")
            return False

        try:
            self.model = Pipeline(
                [
                    (
                        "tfidf",
                        TfidfVectorizer(
                            lowercase=True, stop_words="english", max_features=200
                        ),
                    ),
                    (
                        "classifier",
                        LogisticRegression(max_iter=200, random_state=42),
                    ),
                ]
            )

            self.model.fit(descriptions, categories)
            self.save_model()
            return True
        except Exception as e:
            print(f"Error retraining model: {e}")
            return False


# Example usage / testing
if __name__ == "__main__":
    # Initialize classifier
    classifier = ExpenseClassifier()

    # Test predictions
    test_descriptions = [
        "Uber ride to office",
        "McDonald's burger meal",
        "Netflix monthly subscription",
        "Doctor appointment",
        "Nike shoes purchase",
        "Electricity bill payment",
    ]

    print("Expense Category Predictions:")
    print("=" * 50)
    for desc in test_descriptions:
        result = classifier.predict(desc)
        print(f"Description: {desc}")
        print(f"Category: {result['category']}")
        print(f"Confidence: {result['confidence']}")
        print("-" * 50)
