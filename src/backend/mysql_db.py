import time
import uuid
import pymysql
import pymysql.cursors


def simple_log(message: str):
    print(f"[MySQL]: {message}")


class MySQLClient:
    """
    Simple MySQL connection manager with auto-reconnect
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        db_name: str,
        max_retries: int = 5,
        retry_delay: int = 3,
        connect_timeout: int = 10,
        read_timeout: int = 20,
        write_timeout: int = 20,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.db_name = db_name
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.write_timeout = write_timeout

        self.connection = None

        self.connect()
        self.create_tables()

    def connect(self):
        """Connect the MySQL server with simple retry logic"""
        retries = 0
        while retries < self.max_retries:
            try:
                simple_log(f"(Attempt {retries + 1}) Connecting...")

                self.connection = pymysql.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.db_name,
                    cursorclass=pymysql.cursors.DictCursor,
                    autocommit=True,  # Enable autocommit for simplicity
                    connect_timeout=self.connect_timeout,
                    read_timeout=self.read_timeout,
                    write_timeout=self.write_timeout,
                    charset="utf8",
                )
                simple_log("Connection successful!")
                return

            except pymysql.MySQLError as e:
                simple_log(f"Connection failed: {e}. Retrying...")
                retries += 1
                time.sleep(self.retry_delay)

        raise RuntimeError(
            "Could not connect to the MySQL server after multiple attempts"
        )

    def _ensure_connection(self):
        """Ensures that the connection to MySQL server exists and tries to reconnect if not"""
        try:
            if self.connection is None:
                self.connect()
            else:
                # Check if connection is still open by attempting a simple operation
                self.connection.ping(reconnect=True)
        except (
            pymysql.MySQLError,
            pymysql.OperationalError,
            ValueError,
            OSError,
            Exception,
        ) as e:
            simple_log(f"Lost connection. Reconnecting... ({e})")
            try:
                if self.connection:
                    self.connection.close()
            except:
                pass
            self.connection = None
            self.connect()

    def get_cursor(self):
        """Returns a cursor after ensuring connection"""
        self._ensure_connection()
        try:
            return self.connection.cursor()
        except (pymysql.MySQLError, pymysql.OperationalError, ValueError, OSError) as e:
            simple_log(f"Error getting cursor: {e}. Reconnecting...")
            self._ensure_connection()
            return self.connection.cursor()

    def close(self):
        """Close the active connection if it exists"""
        if self.connection:
            try:
                self.connection.close()
            except pymysql.MySQLError:
                pass
            finally:
                self.connection = None

    def create_tables(self):
        """Create tables if they don't exist"""
        self._ensure_connection()

        # Transactions table schema
        ddl_transactions = """
        CREATE TABLE IF NOT EXISTS `transactions` (
            transaction_id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            currency VARCHAR(10) DEFAULT 'INR',
            category VARCHAR(50),
            description VARCHAR(255),
            transaction_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX (user_id)
        );
        """

        # User summaries table
        ddl_user_summaries = """
        CREATE TABLE IF NOT EXISTS `user_summaries` (
            user_id VARCHAR(50) PRIMARY KEY,
            last_calculated DATE,
            daily_total DECIMAL(10, 2) DEFAULT 0.00,
            weekly_total DECIMAL(10, 2) DEFAULT 0.00,
            monthly_total DECIMAL(10, 2) DEFAULT 0.00,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        );
        """

        cursor = None
        try:
            cursor = self.get_cursor()
            cursor.execute(ddl_transactions)
            cursor.execute(ddl_user_summaries)
            simple_log("Tables created/verified successfully!")
        except pymysql.MySQLError as e:
            simple_log(f"Table creation error: {e}")
        finally:
            if cursor:
                cursor.close()

    def insert_transaction(
        self,
        user_id: str,
        amount: float,
        currency: str,
        category: str,
        description: str,
        transaction_date: str,
    ):
        """
        Insert a new transaction into the database

        Args:
            user_id: User ID from MongoDB
            amount: Transaction amount
            currency: Currency code (e.g., 'INR')
            category: Expense category (e.g., 'Food', 'Transport')
            description: Transaction description
            transaction_date: Date of transaction (YYYY-MM-DD format)

        Returns:
            Transaction ID (UUID string) or None if failed
        """
        # Generate UUID for transaction
        transaction_id = str(uuid.uuid4())

        query = """
        INSERT INTO transactions (transaction_id, user_id, amount, currency, category, description, transaction_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        cursor = None
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                self._ensure_connection()
                cursor = self.get_cursor()
                cursor.execute(
                    query,
                    (
                        transaction_id,
                        user_id,
                        amount,
                        currency,
                        category,
                        description,
                        transaction_date,
                    ),
                )
                simple_log(f"Transaction {transaction_id} inserted for user {user_id}")
                return transaction_id
            except (
                pymysql.MySQLError,
                pymysql.OperationalError,
                ValueError,
                OSError,
            ) as e:
                retry_count += 1
                simple_log(
                    f"Error inserting transaction (attempt {retry_count}/{max_retries}): {e}"
                )
                # Force reconnection on error
                try:
                    if self.connection:
                        self.connection.close()
                except:
                    pass
                self.connection = None

                if retry_count < max_retries:
                    time.sleep(1)
                    continue
                return None
            finally:
                if cursor:
                    try:
                        cursor.close()
                    except:
                        pass

        return None

    def get_transactions_by_user(self, user_id: str, limit: int = 50):
        """
        Retrieve transactions for a specific user

        Args:
            user_id: User ID from MongoDB
            limit: Maximum number of transactions to retrieve

        Returns:
            List of transaction dictionaries
        """
        query = """
        SELECT * FROM transactions 
        WHERE user_id = %s 
        ORDER BY created_at DESC 
        LIMIT %s
        """

        cursor = None
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                self._ensure_connection()
                cursor = self.get_cursor()
                cursor.execute(query, (user_id, limit))
                transactions = cursor.fetchall()
                return transactions if transactions else []
            except (
                pymysql.MySQLError,
                pymysql.OperationalError,
                ValueError,
                OSError,
            ) as e:
                retry_count += 1
                simple_log(
                    f"Error retrieving transactions (attempt {retry_count}/{max_retries}): {e}"
                )
                # Force reconnection on error
                try:
                    if self.connection:
                        self.connection.close()
                except:
                    pass
                self.connection = None

                if retry_count < max_retries:
                    time.sleep(1)  # Wait before retrying
                    continue
                return []
            finally:
                if cursor:
                    try:
                        cursor.close()
                    except:
                        pass

        return []

    def get_weekly_summary(self, user_id: str):
        """
        Get weekly expense summary for a user

        Args:
            user_id: User ID from MongoDB

        Returns:
            Dictionary with daily breakdown for the past 7 days
        """
        query = """
        SELECT DATE(transaction_date) as date, SUM(amount) as total, COUNT(*) as count
        FROM transactions
        WHERE user_id = %s AND transaction_date >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
        GROUP BY DATE(transaction_date)
        ORDER BY date DESC
        """

        cursor = None
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                self._ensure_connection()
                cursor = self.get_cursor()
                cursor.execute(query, (user_id,))
                results = cursor.fetchall()
                return results if results else []
            except (
                pymysql.MySQLError,
                pymysql.OperationalError,
                ValueError,
                OSError,
            ) as e:
                retry_count += 1
                simple_log(
                    f"Error retrieving weekly summary (attempt {retry_count}/{max_retries}): {e}"
                )
                # Force reconnection on error
                try:
                    if self.connection:
                        self.connection.close()
                except:
                    pass
                self.connection = None

                if retry_count < max_retries:
                    time.sleep(1)
                    continue
                return []
            finally:
                if cursor:
                    try:
                        cursor.close()
                    except:
                        pass

        return []

    def upsert_user_summary(
        self,
        user_id: str,
        daily_total: float,
        weekly_total: float,
        monthly_total: float,
        last_calculated: str,
    ):
        """
        Insert or update user summary

        Args:
            user_id: User ID from MongoDB
            daily_total: Total expenses for the day
            weekly_total: Total expenses for the week
            monthly_total: Total expenses for the month
            last_calculated: Date when summary was last calculated (YYYY-MM-DD format)
        """
        self._ensure_connection()

        query = """
        INSERT INTO user_summaries (user_id, daily_total, weekly_total, monthly_total, last_calculated)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            daily_total = VALUES(daily_total),
            weekly_total = VALUES(weekly_total),
            monthly_total = VALUES(monthly_total),
            last_calculated = VALUES(last_calculated),
            updated_at = CURRENT_TIMESTAMP
        """

        cursor = None
        try:
            cursor = self.get_cursor()
            cursor.execute(
                query,
                (user_id, daily_total, weekly_total, monthly_total, last_calculated),
            )
            simple_log(f"User summary updated for user {user_id}")
            return True
        except pymysql.MySQLError as e:
            simple_log(f"Error updating user summary: {e}")
            return False
        finally:
            if cursor:
                cursor.close()

    def delete_transaction(self, transaction_id: str, user_id: str):
        """Delete a specific transaction"""
        self._ensure_connection()
        query = "DELETE FROM transactions WHERE transaction_id = %s AND user_id = %s"

        cursor = None
        try:
            cursor = self.get_cursor()
            cursor.execute(query, (transaction_id, user_id))
            simple_log(f"Transaction {transaction_id} deleted")
            return cursor.rowcount > 0
        except pymysql.MySQLError as e:
            simple_log(f"Error deleting transaction: {e}")
            return False
        finally:
            if cursor:
                cursor.close()

    def update_transaction(self, transaction_id: str, user_id: str, updates: dict):
        """Update a specific transaction"""
        self._ensure_connection()

        allowed_fields = ["amount", "category", "description", "transaction_date"]
        update_fields = []
        values = []

        for field, value in updates.items():
            if field in allowed_fields:
                update_fields.append(f"{field} = %s")
                values.append(value)

        if not update_fields:
            return False

        values.extend([transaction_id, user_id])
        query = f"UPDATE transactions SET {', '.join(update_fields)} WHERE transaction_id = %s AND user_id = %s"

        cursor = None
        try:
            cursor = self.get_cursor()
            cursor.execute(query, tuple(values))
            simple_log(f"Transaction {transaction_id} updated")
            return cursor.rowcount > 0
        except pymysql.MySQLError as e:
            simple_log(f"Error updating transaction: {e}")
            return False
        finally:
            if cursor:
                cursor.close()

    def delete_transactions_by_user(self, user_id: str):
        """
        Delete all transactions for a user (when account is deleted)

        Args:
            user_id: User ID from MongoDB

        Returns:
            True if successful, False otherwise
        """
        self._ensure_connection()

        query = "DELETE FROM transactions WHERE user_id = %s"

        cursor = None
        try:
            cursor = self.get_cursor()
            cursor.execute(query, (user_id,))
            simple_log(f"All transactions deleted for user {user_id}")
            return True
        except pymysql.MySQLError as e:
            simple_log(f"Error deleting transactions: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
