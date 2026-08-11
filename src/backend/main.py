from config import (
    MONGODB_CONNECTION_URI,
    SESSION_EXPIRY,
    ALLOWED_ORIGINS,
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DB_NAME,
)
from utils import (
    hash_password,
    check_password,
    create_expiry_timestamp,
    compare_session_data,
)
from mongo_db import MongoDBClient
from mysql_db import MySQLClient
from expense_classifier import ExpenseClassifier

import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
import numpy as np
from sklearn.linear_model import LinearRegression

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mdb_connection = MongoDBClient(
    MONGODB_CONNECTION_URI, "Fynanz_Data"
)
mysql_connection = MySQLClient(
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB_NAME
)
classifier = ExpenseClassifier()


# ----- Request Models (Pydantic) -----
class RegisterRequest(BaseModel):
    username: str
    first_name: str
    email: str
    password: str
    last_name: str = ""


class LoginRequest(BaseModel):
    identity: str
    password: str


class TransactionRequest(BaseModel):
    amount: float
    currency: str = "INR"
    category: str | None = None
    description: str
    transaction_date: str


# ----- Helper functions -----


def register_new_user(
    username: str, first_name: str, email: str, password: str, last_name: str = ""
):
    user_exists = mdb_connection.find_user({"username": username.strip()})
    email_used = mdb_connection.find_user({"email": email.strip()})

    if user_exists:
        return [False, "Username already exists!"]
    if email_used:
        return [False, "Email already associated with an existing account!"]

    hashed_password = hash_password(password)
    new_user_data = {
        "username": username.strip(),
        "first_name": first_name.strip().title(),
        "last_name": last_name.strip().title(),
        "email": email.strip().lower(),
        "password": hashed_password,
    }

    insert_id = mdb_connection.insert_new_user(new_user_data).inserted_id
    return [True, mdb_connection.find_user({"_id": insert_id})]


def login_user(identity: str, password: str):
    identity = identity.strip()

    if "@" in identity:  # For email login
        query = {"email": identity.lower()}
    else:  # For username login
        query = {"username": identity}

    user = mdb_connection.find_user(query, include_password=True)

    if not user:
        return [False, 1, "User doesn't exist!"]
    else:
        stored_password = user["password"]
        if not check_password(password, stored_password):
            return [False, 2, "Incorrect Password"]
        else:
            old_session = mdb_connection.find_session({"user_id": user["user_id"]})
            if old_session:
                mdb_connection.delete_session({"user_id": user["user_id"]})


            new_session_insert_id = mdb_connection.create_session(
                {"user_id": user["user_id"]}, create_expiry_timestamp(SESSION_EXPIRY)
            ).inserted_id

            new_session = mdb_connection.find_session({"_id": new_session_insert_id})
            return [True, 0, new_session]


def verify_user_session(request: Request):
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        import json
        import base64

        try:
            token_data = auth_header.replace("Bearer ", "")
            decoded = base64.b64decode(token_data).decode("utf-8")
            session_data = json.loads(decoded)
            if not all(
                k in session_data
                for k in ["user_id", "session_id", "csrf_token", "expires_at"]
            ):
                raise HTTPException(
                    status_code=401, detail="Invalid authorization format"
                )
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid authorization format")
    else:
        session_data = {
            "user_id": request.cookies.get("user_id"),
            "session_id": request.cookies.get("session_id"),
            "csrf_token": request.cookies.get("csrf_token"),
            "expires_at": request.cookies.get("expires_at"),
        }

    if None in list(session_data.values()):
        raise HTTPException(status_code=401, detail="Not logged in")
    stored_user = mdb_connection.find_user({"user_id": session_data["user_id"]})
    stored_session = mdb_connection.find_session({"user_id": session_data["user_id"]})

    if not (stored_user and stored_session):
        raise HTTPException(
            status_code=401, detail="Not logged in / Incorrect cookie values"
        )

    if not compare_session_data(
        stored_session, session_data
    ):
        raise HTTPException(status_code=401, detail="Invalid session")

    return [
        stored_user,
    ]


# ----- FastAPI app endpoints -----
@app.get("/")
def root():
    return {
        "api_name": "Fynanz Backend API",
        "api_version": 1,
        "project_info": {
            "project_name": "Fynanz",
            "project_description": "Smart Expense Tracker using Machine Learning",
        },
    }


@app.get("/debug-cookies")
def debug_cookies(request: Request):
    """Debug endpoint to check what cookies the server receives"""
    cookies = {
        "user_id": request.cookies.get("user_id"),
        "session_id": request.cookies.get("session_id"),
        "csrf_token": request.cookies.get("csrf_token"),
        "expires_at": request.cookies.get("expires_at"),
    }
    return {"cookies": cookies, "all_cookies": dict(request.cookies)}


# ----- Authentication Endpoints -----
@app.post("/register")
def register(request: RegisterRequest):
    """Register a new user"""
    success, result = register_new_user(
        request.username,
        request.first_name,
        request.email,
        request.password,
        request.last_name,
    )

    if success:
        return {
            "success": True,
            "message": "User registered successfully!",
            "user": result,
        }
    else:
        raise HTTPException(status_code=400, detail=result)


@app.post("/login")
def login(request: LoginRequest):
    """Login user and create session"""
    success, error_code, result = login_user(request.identity, request.password)

    if success:
        session = result
        user = mdb_connection.find_user({"user_id": session["user_id"]})
        if user:
            mdb_connection.update_login_streak(session["user_id"])

        return {
            "success": True,
            "message": "Login successful!",
            "session": {
                "user_id": str(session["user_id"]),
                "session_id": str(session["session_id"]),
                "csrf_token": str(session["csrf_token"]),
                "expires_at": str(session["expires_at"]),
            },
        }
    else:
        if error_code == 1:
            raise HTTPException(status_code=404, detail="User doesn't exist!")
        else:
            raise HTTPException(status_code=401, detail="Incorrect password!")


@app.post("/logout")
def logout(session=Depends(verify_user_session)):
    """Logout user and delete session"""
    user = session[0]
    mdb_connection.delete_session({"user_id": user["user_id"]})
    return {"success": True, "message": "Logged out successfully"}


@app.get("/test-session-check")
def test_session_check(session=Depends(verify_user_session)):
    """Test endpoint to check if session is valid"""
    user = session[0]
    return {
        "success": True,
        "username": user.get("username", ""),
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", ""),
        "email": user.get("email", ""),
    }


# ----- Transaction Endpoints -----
@app.post("/transactions")
def add_transaction(
    transaction: TransactionRequest, session=Depends(verify_user_session)
):
    """Add a new transaction/expense"""
    user = session[0]
    user_id = user["user_id"]

    category = transaction.category
    if not category:
        result = classifier.predict(transaction.description)
        category = result["category"]

    transaction_id = mysql_connection.insert_transaction(
        user_id=user_id,
        amount=transaction.amount,
        currency=transaction.currency,
        category=category,
        description=transaction.description,
        transaction_date=transaction.transaction_date,
    )

    if transaction_id:
        return {
            "success": True,
            "message": "Transaction added successfully!",
            "category": category,
            "transaction_id": transaction_id,
        }
    else:
        raise HTTPException(status_code=500, detail="Error adding transaction")


@app.get("/transactions")
def get_transactions(limit: int = 50, session=Depends(verify_user_session)):
    """Get all transactions for the logged-in user"""
    user = session[0]
    user_id = user["user_id"]

    transactions = mysql_connection.get_transactions_by_user(user_id, limit)

    return {"success": True, "transactions": transactions, "count": len(transactions)}


@app.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: str, session=Depends(verify_user_session)):
    """Delete a specific transaction"""
    user = session[0]
    user_id = user["user_id"]

    success = mysql_connection.delete_transaction(transaction_id, user_id)

    if success:
        return {"success": True, "message": "Transaction deleted successfully"}
    else:
        raise HTTPException(
            status_code=404, detail="Transaction not found or already deleted"
        )


@app.put("/transactions/{transaction_id}")
def update_transaction(
    transaction_id: str,
    transaction: TransactionRequest,
    session=Depends(verify_user_session),
):
    """Update a specific transaction"""
    user = session[0]
    user_id = user["user_id"]

    updates = {
        "amount": transaction.amount,
        "category": transaction.category,
        "description": transaction.description,
        "transaction_date": transaction.transaction_date,
    }

    success = mysql_connection.update_transaction(transaction_id, user_id, updates)

    if success:
        return {"success": True, "message": "Transaction updated successfully"}
    else:
        raise HTTPException(status_code=404, detail="Transaction not found")


@app.get("/summary/week")
def get_weekly_summary(session=Depends(verify_user_session)):
    """Get weekly expense summary for the logged-in user"""
    user = session[0]
    user_id = user["user_id"]

    summary = mysql_connection.get_weekly_summary(user_id)
    transactions = mysql_connection.get_transactions_by_user(user_id)

    total_weekly = sum(item["total"] if item["total"] else 0 for item in summary)

    return {
        "success": True,
        "total": float(total_weekly),
        "count": len(transactions) if transactions else 0,
    }


@app.get("/predictions")
async def get_spending_predictions(session=Depends(verify_user_session)):
    """
    Get future spending predictions using Linear Regression
    Predicts spending for next 7 days and next 30 days
    """
    user = session[0]
    user_id = user["user_id"]

    transactions = mysql_connection.get_transactions_by_user(user_id, limit=500)

    if not transactions or len(transactions) < 3:
        raise HTTPException(
            status_code=400,
            detail="Not enough data for predictions (minimum 3 transactions required)",
        )

    dates = []
    amounts = []

    for tx in transactions:
        tx_date = tx["transaction_date"]
        if isinstance(tx_date, str):
            tx_date = datetime.strptime(tx_date, "%Y-%m-%d").date()
        elif isinstance(tx_date, datetime):
            tx_date = tx_date.date()

        dates.append(tx_date)
        amounts.append(float(tx["amount"]))

    sorted_data = sorted(zip(dates, amounts), key=lambda x: x[0])
    dates, amounts = zip(*sorted_data)

    first_date = dates[0]
    days_since_start = [(d - first_date).days for d in dates]

    daily_totals = {}
    for day, amount in zip(days_since_start, amounts):
        daily_totals[day] = daily_totals.get(day, 0) + amount

    X = np.array(list(daily_totals.keys())).reshape(-1, 1)
    y = np.array(list(daily_totals.values()))


    if len(X) < 2:
        raise HTTPException(
            status_code=400,
            detail="Not enough unique transaction days for predictions (minimum 2 days required)",
        )

    model = LinearRegression()
    model.fit(X, y)

    from datetime import date

    today = date.today()
    days_to_today = (today - first_date).days

    next_7_days = []
    for i in range(1, 8):
        future_day = days_to_today + i
        predicted_amount = float(max(0, model.predict(np.array([[future_day]]))[0]))
        next_7_days.append(
            {
                "day": i,
                "date": (today + timedelta(days=i)).strftime("%Y-%m-%d"),
                "predicted_amount": round(predicted_amount, 2),
            }
        )

    next_30_days = []
    for i in range(1, 31):
        future_day = days_to_today + i
        predicted_amount = float(max(0, model.predict(np.array([[future_day]]))[0]))
        next_30_days.append(
            {
                "day": i,
                "date": (today + timedelta(days=i)).strftime("%Y-%m-%d"),
                "predicted_amount": round(predicted_amount, 2),
            }
        )

    total_7_days = sum(d["predicted_amount"] for d in next_7_days)
    total_30_days = sum(d["predicted_amount"] for d in next_30_days)

    from sklearn.metrics import r2_score

    predictions = model.predict(X)
    accuracy = float(r2_score(y, predictions))


    if np.isnan(accuracy) or np.isinf(accuracy):
        accuracy = 0.0

    return {
        "message": "Predictions generated successfully",
        "model_accuracy": round(accuracy, 3),
        "next_7_days_total": round(total_7_days, 2),
        "next_30_days_total": round(total_30_days, 2),
        "next_7_days": next_7_days,
        "next_30_days": next_30_days[:7],  # Return first 7 days for UI
        "daily_average_predicted": round(total_30_days / 30, 2),
    }


# ----- Streaks Endpoints -----
@app.get("/streaks")
def get_user_streak(session=Depends(verify_user_session)):
    """Get login streak for the logged-in user"""
    user = session[0]
    user_id = user["user_id"]

    streak_data = mdb_connection.get_user_streak(user_id)

    return {"success": True, "streak": streak_data}


# ----- Badges Endpoints -----
@app.get("/badges")
def get_user_badges(session=Depends(verify_user_session)):
    """Get all badges for the logged-in user and check for new badges"""
    user = session[0]
    user_id = user["user_id"]

    badges = mdb_connection.get_user_badges(user_id)

    transactions = mysql_connection.get_transactions_by_user(user_id, limit=500)


    category_totals = {}
    for tx in transactions:
        category = tx.get("category", "Other")
        amount = float(tx.get("amount", 0))
        category_totals[category] = category_totals.get(category, 0) + amount

    badge_configs = [
        {
            "name": "Foodie",
            "category": "Food & Dining",
            "threshold": 5000,
            "emoji": "🍔",
            "description": "Spent ₹5,000+ on Food & Dining",
        },
        {
            "name": "Shopaholic",
            "category": "Shopping",
            "threshold": 10000,
            "emoji": "🛍️",
            "description": "Spent ₹10,000+ on Shopping",
        },
        {
            "name": "Traveler",
            "category": "Transport",
            "threshold": 3000,
            "emoji": "🚗",
            "description": "Spent ₹3,000+ on Transport",
        },
        {
            "name": "Entertainment Guru",
            "category": "Entertainment",
            "threshold": 5000,
            "emoji": "🎮",
            "description": "Spent ₹5,000+ on Entertainment",
        },
        {
            "name": "Health Conscious",
            "category": "Healthcare",
            "threshold": 5000,
            "emoji": "🏥",
            "description": "Spent ₹5,000+ on Healthcare",
        },
        {
            "name": "Scholar",
            "category": "Education",
            "threshold": 10000,
            "emoji": "📚",
            "description": "Spent ₹10,000+ on Education",
        },
    ]

    existing_badge_names = [b["badge_name"] for b in badges]
    new_badges = []

    for config in badge_configs:
        if config["name"] not in existing_badge_names:
            category_spending = category_totals.get(config["category"], 0)
            if category_spending >= config["threshold"]:
                new_badge = mdb_connection.add_badge(
                    user_id,
                    config["name"],
                    {
                        "emoji": config["emoji"],
                        "description": config["description"],
                        "category": config["category"],
                        "threshold": config["threshold"],
                    },
                )
                new_badges.append(config["name"])
                badges.append(new_badge)

    tx_count_badges = [
        {
            "name": "Beginner",
            "count": 10,
            "emoji": "🌱",
            "description": "Made your first 10 transactions",
        },
        {
            "name": "Regular",
            "count": 50,
            "emoji": "⭐",
            "description": "Made 50 transactions",
        },
        {
            "name": "Expert",
            "count": 100,
            "emoji": "💎",
            "description": "Made 100 transactions",
        },
        {
            "name": "Master",
            "count": 250,
            "emoji": "👑",
            "description": "Made 250 transactions",
        },
    ]

    tx_count = len(transactions)
    for config in tx_count_badges:
        if config["name"] not in existing_badge_names:
            if tx_count >= config["count"]:
                new_badge = mdb_connection.add_badge(
                    user_id,
                    config["name"],
                    {
                        "emoji": config["emoji"],
                        "description": config["description"],
                        "type": "transaction_count",
                        "count": config["count"],
                    },
                )
                new_badges.append(config["name"])
                badges.append(new_badge)

    return {
        "success": True,
        "badges": badges,
        "new_badges": new_badges,
        "count": len(badges),
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app", host="0.0.0.0", port=8000, server_header=False, reload=False
    )
