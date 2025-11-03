#!/usr/bin/env python3
"""
Comprehensive Supabase Upload Script
====================================

This script handles the complete migration of the message-extractor database
from SQLite to Supabase, including:
- Schema creation with all tables, indexes, triggers, and views
- Data migration with referential integrity
- Comprehensive testing and verification
- Detailed logging and error reporting

Project: message_extractor
Email: marwan@marwanrefaat.com
Author: Message Extractor Team

Usage:
    python scripts/upload_to_supabase.py --connection-string "postgresql://..."
    OR
    python scripts/upload_to_supabase.py --project-ref xyz --password pwd
    
Environment Variables:
    SUPABASE_CONNECTION - Full PostgreSQL connection string
    SUPABASE_PROJECT_REF - Project reference ID
    SUPABASE_PASSWORD - Database password
"""

import argparse
import sys
import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import re

try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    from psycopg2.extras import execute_values, RealDictCursor
except ImportError:
    print("❌ psycopg2 not installed. Install it with:")
    print("   pip install psycopg2-binary")
    sys.exit(1)


class SupabaseUploader:
    """
    Handles complete migration from SQLite to Supabase
    """
    
    def __init__(self, connection_params: Dict[str, str], sqlite_path: str, 
                 migration_sql_path: Optional[str] = None):
        """
        Initialize uploader
        
        Args:
            connection_params: PostgreSQL connection parameters
            sqlite_path: Path to SQLite database
            migration_sql_path: Path to SQL migration file
        """
        self.connection_params = connection_params
        self.sqlite_path = Path(sqlite_path)
        self.migration_sql_path = Path(migration_sql_path) if migration_sql_path else None
        
        if not self.sqlite_path.exists():
            raise FileNotFoundError(f"SQLite database not found: {self.sqlite_path}")
        
        self.pg_conn = None
        self.sqlite_conn = None
        self.stats = {
            'contacts': 0,
            'conversations': 0,
            'messages': 0,
            'participants': 0,
            'calendar_events': 0,
            'message_tags': 0,
            'errors': []
        }
    
    def connect(self):
        """Establish connections to both databases"""
        print("🔌 Connecting to databases...")
        
        # Connect to PostgreSQL/Supabase
        try:
            self.pg_conn = psycopg2.connect(**self.connection_params)
            self.pg_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            print(f"   ✅ Connected to Supabase: {self.connection_params['host']}")
        except Exception as e:
            print(f"   ❌ Failed to connect to Supabase: {e}")
            raise
        
        # Connect to SQLite
        try:
            self.sqlite_conn = sqlite3.connect(self.sqlite_path)
            self.sqlite_conn.row_factory = sqlite3.Row
            print(f"   ✅ Connected to SQLite: {self.sqlite_path}")
        except Exception as e:
            print(f"   ❌ Failed to connect to SQLite: {e}")
            raise
    
    def close(self):
        """Close database connections"""
        if self.pg_conn:
            self.pg_conn.close()
        if self.sqlite_conn:
            self.sqlite_conn.close()
    
    def create_schema(self):
        """Create database schema from migration SQL file"""
        print("\n📐 Creating database schema...")
        
        if not self.migration_sql_path or not self.migration_sql_path.exists():
            # Use default path
            self.migration_sql_path = Path(__file__).parent.parent / 'data' / 'database' / 'supabase_migration.sql'
        
        if not self.migration_sql_path.exists():
            raise FileNotFoundError(f"Migration SQL file not found: {self.migration_sql_path}")
        
        print(f"   📄 Reading migration file: {self.migration_sql_path}")
        
        # Read SQL file
        with open(self.migration_sql_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Split into statements (simple approach - handles function definitions)
        statements = self._split_sql_statements(sql_content)
        print(f"   📊 Found {len(statements)} SQL statements")
        
        # Execute statements
        cursor = self.pg_conn.cursor()
        executed = 0
        errors = []
        
        for i, statement in enumerate(statements, 1):
            if not statement.strip() or statement.strip().startswith('--'):
                continue
            
            try:
                cursor.execute(statement)
                executed += 1
                if i % 20 == 0:
                    print(f"   ⏳ Executed {i}/{len(statements)} statements...")
            except Exception as e:
                error_msg = str(e)
                # Ignore "already exists" errors for IF NOT EXISTS statements
                if 'already exists' not in error_msg.lower():
                    errors.append((i, statement[:100], error_msg))
                    print(f"   ⚠️  Warning on statement {i}: {error_msg[:80]}")
        
        cursor.close()
        
        print(f"   ✅ Schema creation complete: {executed} statements executed")
        if errors:
            print(f"   ⚠️  {len(errors)} warnings (non-critical)")
        
        # Verify tables
        self._verify_schema()
    
    def _split_sql_statements(self, sql_content: str) -> List[str]:
        """Split SQL content into individual statements"""
        statements = []
        current = []
        in_function = False
        dollar_quote = None
        
        for line in sql_content.split('\n'):
            stripped = line.strip()
            
            # Skip empty lines and comments at start
            if not stripped or stripped.startswith('--'):
                if current:  # Keep comments inside statements
                    current.append(line)
                continue
            
            # Detect function definitions with $$ delimiters
            if '$$' in line:
                dollar_quotes = re.findall(r'\$\$[^\$]*\$\$|\$\$', line)
                if dollar_quotes:
                    if not in_function:
                        in_function = True
                        dollar_quote = dollar_quotes[0]
                    elif dollar_quote in line:
                        in_function = False
                        dollar_quote = None
            
            current.append(line)
            
            # End of statement (not in function)
            if not in_function and stripped.endswith(';'):
                statement = '\n'.join(current).strip()
                if statement:
                    statements.append(statement)
                current = []
        
        # Add any remaining statement
        if current:
            remaining = '\n'.join(current).strip()
            if remaining:
                statements.append(remaining)
        
        return statements
    
    def _verify_schema(self):
        """Verify that all required tables exist"""
        print("\n   🔍 Verifying schema...")
        
        cursor = self.pg_conn.cursor()
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        
        expected_tables = [
            'contacts', 'conversations', 'messages', 
            'conversation_participants', 'calendar_events', 'message_tags'
        ]
        
        missing = set(expected_tables) - set(tables)
        if missing:
            print(f"   ⚠️  Missing tables: {', '.join(missing)}")
            return False
        
        print(f"   ✅ All {len(expected_tables)} tables verified")
        return True
    
    def migrate_data(self, batch_size: int = 100):
        """
        Migrate all data from SQLite to Supabase
        
        Args:
            batch_size: Number of rows to insert per batch
        """
        print("\n📦 Migrating data from SQLite to Supabase...")
        print(f"   Using batch size: {batch_size}")
        
        try:
            # Migrate in correct order (respecting foreign keys)
            self._migrate_contacts(batch_size)
            self._migrate_conversations(batch_size)
            self._migrate_messages(batch_size)
            self._migrate_participants(batch_size)
            self._migrate_calendar_events(batch_size)
            self._migrate_message_tags(batch_size)
            
            print("\n✅ Data migration complete!")
            self._print_migration_stats()
            
        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            raise
    
    def _migrate_contacts(self, batch_size: int):
        """Migrate contacts table"""
        print("\n   📇 Migrating contacts...")
        
        # Fetch from SQLite
        cursor_sqlite = self.sqlite_conn.cursor()
        cursor_sqlite.execute("SELECT * FROM contacts")
        rows = cursor_sqlite.fetchall()
        
        if not rows:
            print("   ℹ️  No contacts to migrate")
            return
        
        # Prepare data for PostgreSQL
        data = []
        for row in rows:
            data.append((
                row['contact_id'],
                row['display_name'],
                row['email'],
                row['phone'],
                row['platform'],
                row['platform_id'],
                self._convert_timestamp(row.get('first_seen')),
                self._convert_timestamp(row.get('last_seen')),
                row.get('message_count', 0),
                bool(row.get('is_me', False)),
                bool(row.get('is_validated', False))
            ))
        
        # Insert into PostgreSQL (with ID preservation for foreign keys)
        cursor_pg = self.pg_conn.cursor()
        
        # Temporarily disable triggers to avoid conflicts
        cursor_pg.execute("SET session_replication_role = 'replica';")
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i+batch_size]
            execute_values(
                cursor_pg,
                """
                INSERT INTO contacts (
                    contact_id, display_name, email, phone, platform, platform_id,
                    first_seen, last_seen, message_count, is_me, is_validated
                ) VALUES %s
                ON CONFLICT (platform, platform_id) DO NOTHING
                """,
                batch,
                template=None,
                page_size=batch_size
            )
            print(f"   ⏳ Migrated {min(i+batch_size, len(data))}/{len(data)} contacts...")
        
        # Re-enable triggers and reset sequence
        cursor_pg.execute("SET session_replication_role = 'origin';")
        cursor_pg.execute("SELECT setval('contacts_contact_id_seq', (SELECT MAX(contact_id) FROM contacts));")
        
        self.stats['contacts'] = len(data)
        cursor_pg.close()
        cursor_sqlite.close()
        print(f"   ✅ Migrated {len(data)} contacts")
    
    def _migrate_conversations(self, batch_size: int):
        """Migrate conversations table"""
        print("\n   💬 Migrating conversations...")
        
        cursor_sqlite = self.sqlite_conn.cursor()
        cursor_sqlite.execute("SELECT * FROM conversations")
        rows = cursor_sqlite.fetchall()
        
        if not rows:
            print("   ℹ️  No conversations to migrate")
            return
        
        data = []
        for row in rows:
            data.append((
                row['conversation_id'],
                row.get('conversation_name'),
                row['platform'],
                row.get('thread_id'),
                self._convert_timestamp(row.get('first_message_at')),
                self._convert_timestamp(row.get('last_message_at')),
                row.get('message_count', 0),
                bool(row.get('is_group', False)),
                row.get('participant_count', 2),
                bool(row.get('is_important', False)),
                row.get('category')
            ))
        
        cursor_pg = self.pg_conn.cursor()
        cursor_pg.execute("SET session_replication_role = 'replica';")
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i+batch_size]
            execute_values(
                cursor_pg,
                """
                INSERT INTO conversations (
                    conversation_id, conversation_name, platform, thread_id,
                    first_message_at, last_message_at, message_count, is_group,
                    participant_count, is_important, category
                ) VALUES %s
                ON CONFLICT (conversation_id) DO NOTHING
                """,
                batch,
                page_size=batch_size
            )
            print(f"   ⏳ Migrated {min(i+batch_size, len(data))}/{len(data)} conversations...")
        
        cursor_pg.execute("SET session_replication_role = 'origin';")
        cursor_pg.execute("SELECT setval('conversations_conversation_id_seq', (SELECT MAX(conversation_id) FROM conversations));")
        
        self.stats['conversations'] = len(data)
        cursor_pg.close()
        cursor_sqlite.close()
        print(f"   ✅ Migrated {len(data)} conversations")
    
    def _migrate_messages(self, batch_size: int):
        """Migrate messages table"""
        print("\n   📨 Migrating messages...")
        
        cursor_sqlite = self.sqlite_conn.cursor()
        cursor_sqlite.execute("SELECT * FROM messages")
        rows = cursor_sqlite.fetchall()
        
        if not rows:
            print("   ℹ️  No messages to migrate")
            return
        
        data = []
        for row in rows:
            # Parse JSON if present
            raw_data = None
            if row.get('raw_data'):
                try:
                    raw_data = json.loads(row['raw_data']) if isinstance(row['raw_data'], str) else row['raw_data']
                except:
                    raw_data = None
            
            data.append((
                row['message_id'],
                row['platform'],
                row['platform_message_id'],
                row['conversation_id'],
                row['sender_id'],
                self._convert_timestamp(row['timestamp']),
                row.get('timezone'),
                row['body'],
                row.get('subject'),
                bool(row.get('is_read')) if row.get('is_read') is not None else None,
                bool(row.get('is_starred')) if row.get('is_starred') is not None else None,
                bool(row.get('is_sent', True)),
                bool(row.get('is_deleted', False)),
                bool(row.get('is_reply', False)),
                row.get('reply_to_message_id'),
                bool(row.get('has_attachment', False)),
                bool(row.get('is_tapback', False)),
                row.get('tapback_type'),
                json.dumps(raw_data) if raw_data else None
            ))
        
        cursor_pg = self.pg_conn.cursor()
        cursor_pg.execute("SET session_replication_role = 'replica';")
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i+batch_size]
            execute_values(
                cursor_pg,
                """
                INSERT INTO messages (
                    message_id, platform, platform_message_id, conversation_id, sender_id,
                    timestamp, timezone, body, subject, is_read, is_starred, is_sent,
                    is_deleted, is_reply, reply_to_message_id, has_attachment, is_tapback,
                    tapback_type, raw_data
                ) VALUES %s
                ON CONFLICT (platform, platform_message_id) DO NOTHING
                """,
                batch,
                page_size=batch_size
            )
            print(f"   ⏳ Migrated {min(i+batch_size, len(data))}/{len(data)} messages...")
        
        cursor_pg.execute("SET session_replication_role = 'origin';")
        cursor_pg.execute("SELECT setval('messages_message_id_seq', (SELECT MAX(message_id) FROM messages));")
        
        self.stats['messages'] = len(data)
        cursor_pg.close()
        cursor_sqlite.close()
        print(f"   ✅ Migrated {len(data)} messages")
    
    def _migrate_participants(self, batch_size: int):
        """Migrate conversation_participants table"""
        print("\n   👥 Migrating conversation participants...")
        
        cursor_sqlite = self.sqlite_conn.cursor()
        cursor_sqlite.execute("SELECT * FROM conversation_participants")
        rows = cursor_sqlite.fetchall()
        
        if not rows:
            print("   ℹ️  No participants to migrate")
            return
        
        data = []
        for row in rows:
            data.append((
                row['participant_id'],
                row['conversation_id'],
                row['contact_id'],
                row.get('role', 'member'),
                self._convert_timestamp(row.get('joined_at')),
                self._convert_timestamp(row.get('left_at')),
                row.get('message_count', 0)
            ))
        
        cursor_pg = self.pg_conn.cursor()
        cursor_pg.execute("SET session_replication_role = 'replica';")
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i+batch_size]
            execute_values(
                cursor_pg,
                """
                INSERT INTO conversation_participants (
                    participant_id, conversation_id, contact_id, role,
                    joined_at, left_at, message_count
                ) VALUES %s
                ON CONFLICT (conversation_id, contact_id) DO NOTHING
                """,
                batch,
                page_size=batch_size
            )
            print(f"   ⏳ Migrated {min(i+batch_size, len(data))}/{len(data)} participants...")
        
        cursor_pg.execute("SET session_replication_role = 'origin';")
        cursor_pg.execute("SELECT setval('conversation_participants_participant_id_seq', (SELECT MAX(participant_id) FROM conversation_participants));")
        
        self.stats['participants'] = len(data)
        cursor_pg.close()
        cursor_sqlite.close()
        print(f"   ✅ Migrated {len(data)} participants")
    
    def _migrate_calendar_events(self, batch_size: int):
        """Migrate calendar_events table"""
        print("\n   📅 Migrating calendar events...")
        
        cursor_sqlite = self.sqlite_conn.cursor()
        cursor_sqlite.execute("SELECT * FROM calendar_events")
        rows = cursor_sqlite.fetchall()
        
        if not rows:
            print("   ℹ️  No calendar events to migrate")
            return
        
        data = []
        for row in rows:
            data.append((
                row['event_id'],
                row['message_id'],
                self._convert_timestamp(row['event_start']),
                self._convert_timestamp(row.get('event_end')),
                row.get('event_duration_seconds'),
                row.get('event_location'),
                row.get('event_status'),
                bool(row.get('is_recurring', False)),
                row.get('recurrence_pattern')
            ))
        
        cursor_pg = self.pg_conn.cursor()
        cursor_pg.execute("SET session_replication_role = 'replica';")
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i+batch_size]
            execute_values(
                cursor_pg,
                """
                INSERT INTO calendar_events (
                    event_id, message_id, event_start, event_end, event_duration_seconds,
                    event_location, event_status, is_recurring, recurrence_pattern
                ) VALUES %s
                ON CONFLICT (message_id) DO NOTHING
                """,
                batch,
                page_size=batch_size
            )
            print(f"   ⏳ Migrated {min(i+batch_size, len(data))}/{len(data)} calendar events...")
        
        cursor_pg.execute("SET session_replication_role = 'origin';")
        cursor_pg.execute("SELECT setval('calendar_events_event_id_seq', (SELECT MAX(event_id) FROM calendar_events));")
        
        self.stats['calendar_events'] = len(data)
        cursor_pg.close()
        cursor_sqlite.close()
        print(f"   ✅ Migrated {len(data)} calendar events")
    
    def _migrate_message_tags(self, batch_size: int):
        """Migrate message_tags table"""
        print("\n   🏷️  Migrating message tags...")
        
        cursor_sqlite = self.sqlite_conn.cursor()
        cursor_sqlite.execute("SELECT * FROM message_tags")
        rows = cursor_sqlite.fetchall()
        
        if not rows:
            print("   ℹ️  No message tags to migrate")
            return
        
        data = []
        for row in rows:
            data.append((
                row['tag_id'],
                row['message_id'],
                row['tag_name'],
                row.get('tag_value'),
                self._convert_timestamp(row.get('created_at'))
            ))
        
        cursor_pg = self.pg_conn.cursor()
        cursor_pg.execute("SET session_replication_role = 'replica';")
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i+batch_size]
            execute_values(
                cursor_pg,
                """
                INSERT INTO message_tags (
                    tag_id, message_id, tag_name, tag_value, created_at
                ) VALUES %s
                ON CONFLICT (tag_id) DO NOTHING
                """,
                batch,
                page_size=batch_size
            )
            print(f"   ⏳ Migrated {min(i+batch_size, len(data))}/{len(data)} message tags...")
        
        cursor_pg.execute("SET session_replication_role = 'origin';")
        cursor_pg.execute("SELECT setval('message_tags_tag_id_seq', (SELECT MAX(tag_id) FROM message_tags));")
        
        self.stats['message_tags'] = len(data)
        cursor_pg.close()
        cursor_sqlite.close()
        print(f"   ✅ Migrated {len(data)} message tags")
    
    def _convert_timestamp(self, value: Any) -> Optional[str]:
        """Convert SQLite timestamp to PostgreSQL timestamp"""
        if value is None:
            return None
        
        if isinstance(value, str):
            # Try to parse and format
            try:
                # Handle various formats
                for fmt in [
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%d %H:%M:%S.%f',
                    '%Y-%m-%dT%H:%M:%S',
                    '%Y-%m-%dT%H:%M:%S.%f',
                    '%Y-%m-%dT%H:%M:%SZ'
                ]:
                    try:
                        dt = datetime.strptime(value, fmt)
                        return dt.isoformat()
                    except ValueError:
                        continue
                # If all fail, return as-is (PostgreSQL will handle it)
                return value
            except:
                return value
        
        return value.isoformat() if hasattr(value, 'isoformat') else str(value)
    
    def _print_migration_stats(self):
        """Print migration statistics"""
        print("\n" + "="*60)
        print("📊 MIGRATION STATISTICS")
        print("="*60)
        print(f"   Contacts:        {self.stats['contacts']:>6,}")
        print(f"   Conversations:  {self.stats['conversations']:>6,}")
        print(f"   Messages:       {self.stats['messages']:>6,}")
        print(f"   Participants:   {self.stats['participants']:>6,}")
        print(f"   Calendar Events:{self.stats['calendar_events']:>6,}")
        print(f"   Message Tags:   {self.stats['message_tags']:>6,}")
        print("="*60)
    
    def verify_migration(self):
        """Verify that data was migrated correctly"""
        print("\n🔍 Verifying migration...")
        
        cursor_pg = self.pg_conn.cursor()
        cursor_sqlite = self.sqlite_conn.cursor()
        
        tables = [
            ('contacts', 'contact_id'),
            ('conversations', 'conversation_id'),
            ('messages', 'message_id'),
            ('conversation_participants', 'participant_id'),
            ('calendar_events', 'event_id'),
            ('message_tags', 'tag_id')
        ]
        
        all_good = True
        for table_name, id_column in tables:
            cursor_sqlite.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            sqlite_count = cursor_sqlite.fetchone()['count']
            
            cursor_pg.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            pg_count = cursor_pg.fetchone()[0]
            
            status = "✅" if sqlite_count == pg_count else "❌"
            print(f"   {status} {table_name:25s} SQLite: {sqlite_count:>5,} | Supabase: {pg_count:>5,}")
            
            if sqlite_count != pg_count:
                all_good = False
                self.stats['errors'].append(f"{table_name}: count mismatch ({sqlite_count} vs {pg_count})")
        
        cursor_pg.close()
        cursor_sqlite.close()
        
        if all_good:
            print("\n✅ All tables verified successfully!")
        else:
            print("\n⚠️  Some tables have count mismatches. Check errors above.")
        
        return all_good
    
    def test_queries(self):
        """Run test queries to ensure everything works"""
        print("\n🧪 Running test queries...")
        
        cursor = self.pg_conn.cursor(cursor_factory=RealDictCursor)
        
        tests = [
            ("Recent conversations", "SELECT COUNT(*) FROM recent_conversations"),
            ("Contact statistics", "SELECT COUNT(*) FROM contact_statistics"),
            ("Platform summary", "SELECT * FROM platform_summary"),
            ("Messages with contacts", """
                SELECT COUNT(*) FROM messages m
                JOIN contacts c ON m.sender_id = c.contact_id
                LIMIT 10
            """),
            ("Conversation participants", """
                SELECT COUNT(*) FROM conversation_participants cp
                JOIN conversations conv ON cp.conversation_id = conv.conversation_id
                JOIN contacts c ON cp.contact_id = c.contact_id
            """)
        ]
        
        all_passed = True
        for test_name, query in tests:
            try:
                cursor.execute(query)
                result = cursor.fetchone()
                print(f"   ✅ {test_name}: Query executed successfully")
            except Exception as e:
                print(f"   ❌ {test_name}: {str(e)[:80]}")
                all_passed = False
        
        cursor.close()
        
        if all_passed:
            print("\n✅ All test queries passed!")
        else:
            print("\n⚠️  Some test queries failed.")
        
        return all_passed


def parse_connection_string(connection_string: str) -> Dict[str, str]:
    """Parse PostgreSQL connection string"""
    pattern = r'postgresql://([^:]+):([^@]+)@([^:/]+):?(\d+)?/(.+)'
    match = re.match(pattern, connection_string)
    if not match:
        raise ValueError("Invalid connection string format")
    
    user, password, host, port, database = match.groups()
    return {
        'host': host,
        'port': port or '5432',
        'database': database,
        'user': user,
        'password': password
    }


def build_connection_string(host: str, password: str, project_ref: str, port: int = 5432) -> Dict[str, str]:
    """Build connection string from components"""
    if not host.startswith('db.'):
        host = f'db.{project_ref}.supabase.co'
    
    return {
        'host': host,
        'port': str(port),
        'database': 'postgres',
        'user': 'postgres',
        'password': password
    }


def main():
    parser = argparse.ArgumentParser(
        description='Upload message-extractor database to Supabase',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using connection string
  python scripts/upload_to_supabase.py \\
    --connection-string "postgresql://postgres:password@db.xyz.supabase.co:5432/postgres"
  
  # Using individual parameters
  python scripts/upload_to_supabase.py \\
    --project-ref xyzabc123 \\
    --password yourpassword
  
  # From environment variable
  export SUPABASE_CONNECTION="postgresql://..."
  python scripts/upload_to_supabase.py --connection-string "$SUPABASE_CONNECTION"
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--connection-string', help='Full PostgreSQL connection string')
    group.add_argument('--project-ref', help='Supabase project reference (e.g., xyzabc123)')
    
    parser.add_argument('--password', help='Database password (required with --project-ref)')
    parser.add_argument('--host', help='Database host (optional, auto-generated from project-ref)')
    parser.add_argument('--port', type=int, default=5432, help='Database port (default: 5432)')
    parser.add_argument('--sqlite-db', default='data/database/chats.db', 
                       help='Path to SQLite database (default: data/database/chats.db)')
    parser.add_argument('--migration-sql', default='data/database/supabase_migration.sql',
                       help='Path to SQL migration file')
    parser.add_argument('--batch-size', type=int, default=100,
                       help='Batch size for data migration (default: 100)')
    parser.add_argument('--skip-schema', action='store_true',
                       help='Skip schema creation (use if schema already exists)')
    parser.add_argument('--skip-verification', action='store_true',
                       help='Skip verification and testing')
    
    args = parser.parse_args()
    
    # Build connection parameters
    if args.connection_string:
        connection_params = parse_connection_string(args.connection_string)
    elif args.project_ref:
        if not args.password:
            parser.error("--password is required when using --project-ref")
        connection_params = build_connection_string(
            args.host or '',
            args.password,
            args.project_ref,
            args.port
        )
    else:
        conn_str = os.getenv('SUPABASE_CONNECTION')
        if conn_str:
            connection_params = parse_connection_string(conn_str)
        else:
            parser.error("Must provide --connection-string or --project-ref")
    
    # Create uploader
    sqlite_path = Path(__file__).parent.parent / args.sqlite_db
    migration_sql = Path(__file__).parent.parent / args.migration_sql
    
    print("="*70)
    print("🚀 SUPABASE DATABASE UPLOAD")
    print("="*70)
    print(f"Project: message_extractor")
    print(f"Email: marwan@marwanrefaat.com")
    print(f"SQLite DB: {sqlite_path}")
    print(f"Supabase: {connection_params['host']}")
    print("="*70)
    
    uploader = None
    try:
        uploader = SupabaseUploader(connection_params, str(sqlite_path), str(migration_sql))
        uploader.connect()
        
        # Create schema
        if not args.skip_schema:
            uploader.create_schema()
        else:
            print("\n⏭️  Skipping schema creation...")
        
        # Migrate data
        uploader.migrate_data(batch_size=args.batch_size)
        
        # Verify
        if not args.skip_verification:
            uploader.verify_migration()
            uploader.test_queries()
        
        print("\n" + "="*70)
        print("✅ UPLOAD COMPLETE!")
        print("="*70)
        print(f"\nYour database is now live on Supabase at:")
        print(f"  Host: {connection_params['host']}")
        print(f"  Database: {connection_params['database']}")
        print(f"\nYou can now access it via:")
        print(f"  - Supabase Dashboard: https://supabase.com/dashboard")
        print(f"  - Connection String: postgresql://{connection_params['user']}:***@{connection_params['host']}:{connection_params['port']}/{connection_params['database']}")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ Upload failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        if uploader:
            uploader.close()


if __name__ == '__main__':
    main()

