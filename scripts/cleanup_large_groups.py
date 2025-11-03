#!/usr/bin/env python3
"""
Cleanup script to remove large group chats (>7 participants) from Supabase

This script removes conversations, messages, and participants for:
- WhatsApp groups with more than 7 participants
- iMessage groups with more than 7 participants

Usage:
    python scripts/cleanup_large_groups.py --connection-string "postgresql://..."
    OR
    python scripts/cleanup_large_groups.py --project-ref xyz --password pwd
"""

import argparse
import sys
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("❌ psycopg2 not installed. Install it with:")
    print("   pip install psycopg2-binary")
    sys.exit(1)


class LargeGroupCleanup:
    """Remove large group chats from Supabase"""
    
    def __init__(self, connection_params: Dict[str, str], connection_string: Optional[str] = None):
        """
        Initialize cleanup
        
        Args:
            connection_params: PostgreSQL connection parameters
            connection_string: Full connection string (for pooler connections)
        """
        self.connection_params = connection_params
        self.connection_string = connection_string
        self.pg_conn = None
        self.stats = {
            'conversations_deleted': 0,
            'messages_deleted': 0,
            'participants_deleted': 0,
            'calendar_events_deleted': 0,
            'message_tags_deleted': 0
        }
    
    def connect(self):
        """Establish connection to PostgreSQL/Supabase"""
        print("🔌 Connecting to Supabase...")
        
        try:
            # Use connection string directly for pooler (avoids encoding issues)
            if self.connection_string and 'pooler' in self.connection_string.lower():
                dsn = self.connection_string.replace('postgres://', 'postgresql://')
                self.pg_conn = psycopg2.connect(dsn)
            else:
                connection_params = self.connection_params.copy()
                if 'client_encoding' not in connection_params:
                    connection_params['client_encoding'] = 'UTF8'
                self.pg_conn = psycopg2.connect(**connection_params)
            
            self.pg_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            host = self.connection_params.get('host', 'unknown')
            print(f"   ✅ Connected to Supabase: {host}")
        except Exception as e:
            print(f"   ❌ Failed to connect to Supabase: {e}")
            raise
    
    def close(self):
        """Close database connection"""
        if self.pg_conn:
            self.pg_conn.close()
    
    def cleanup(self, dry_run: bool = False):
        """Remove large group chats from Supabase"""
        print("\n🧹 Cleaning up large group chats (>7 participants)...")
        
        if dry_run:
            print("   🔍 DRY RUN MODE - No changes will be made")
        
        cursor = self.pg_conn.cursor()
        
        # Find all large group chats for WhatsApp and iMessage
        cursor.execute("""
            SELECT conversation_id, conversation_name, platform, participant_count
            FROM conversations
            WHERE platform IN ('whatsapp', 'imessage')
            AND participant_count > 7
        """)
        
        large_groups = cursor.fetchall()
        
        if not large_groups:
            print("   ℹ️  No large group chats found to remove")
            return
        
        print(f"   📊 Found {len(large_groups)} large group chats to remove")
        
        for conv_id, conv_name, platform, participant_count in large_groups:
            print(f"   🗑️  {platform}: {conv_name or 'Unnamed'} ({participant_count} participants)")
        
        if dry_run:
            print("\n   ⏭️  DRY RUN - Would delete:")
            print(f"      - {len(large_groups)} conversations")
            print(f"      - Messages, participants, and related data")
            return
        
        # Get conversation IDs
        conv_ids = [row[0] for row in large_groups]
        
        # Delete in order (respecting foreign keys)
        # 1. Message tags (depends on messages)
        cursor.execute("""
            DELETE FROM message_tags
            WHERE message_id IN (
                SELECT message_id FROM messages WHERE conversation_id = ANY(%s)
            )
        """, (conv_ids,))
        self.stats['message_tags_deleted'] = cursor.rowcount
        
        # 2. Calendar events (depends on messages)
        cursor.execute("""
            DELETE FROM calendar_events
            WHERE message_id IN (
                SELECT message_id FROM messages WHERE conversation_id = ANY(%s)
            )
        """, (conv_ids,))
        self.stats['calendar_events_deleted'] = cursor.rowcount
        
        # 3. Messages (depends on conversations)
        cursor.execute("""
            DELETE FROM messages
            WHERE conversation_id = ANY(%s)
        """, (conv_ids,))
        self.stats['messages_deleted'] = cursor.rowcount
        
        # 4. Conversation participants (depends on conversations)
        cursor.execute("""
            DELETE FROM conversation_participants
            WHERE conversation_id = ANY(%s)
        """, (conv_ids,))
        self.stats['participants_deleted'] = cursor.rowcount
        
        # 5. Conversations (final)
        cursor.execute("""
            DELETE FROM conversations
            WHERE conversation_id = ANY(%s)
        """, (conv_ids,))
        self.stats['conversations_deleted'] = cursor.rowcount
        
        cursor.close()
        
        print("\n✅ Cleanup complete!")
        self._print_stats()
    
    def _print_stats(self):
        """Print cleanup statistics"""
        print("\n" + "="*60)
        print("📊 CLEANUP STATISTICS")
        print("="*60)
        print(f"   Conversations deleted:  {self.stats['conversations_deleted']:>6,}")
        print(f"   Messages deleted:       {self.stats['messages_deleted']:>6,}")
        print(f"   Participants deleted:   {self.stats['participants_deleted']:>6,}")
        print(f"   Calendar events deleted: {self.stats['calendar_events_deleted']:>6,}")
        print(f"   Message tags deleted:    {self.stats['message_tags_deleted']:>6,}")
        print("="*60)


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
    if host and host.strip():
        if 'pooler' in host:
            user = f'postgres.{project_ref}'
        else:
            user = 'postgres'
    else:
        host = f'db.{project_ref}.supabase.co'
        user = 'postgres'
    
    return {
        'host': host,
        'port': str(port),
        'database': 'postgres',
        'user': user,
        'password': password,
        'sslmode': 'require'
    }


def main():
    parser = argparse.ArgumentParser(
        description='Remove large group chats (>7 participants) from Supabase',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using connection string
  python scripts/cleanup_large_groups.py \\
    --connection-string "postgresql://postgres:password@db.xyz.supabase.co:5432/postgres"
  
  # Using individual parameters
  python scripts/cleanup_large_groups.py \\
    --project-ref xyzabc123 \\
    --password yourpassword
  
  # Dry run (see what would be deleted)
  python scripts/cleanup_large_groups.py \\
    --project-ref xyzabc123 \\
    --password yourpassword \\
    --dry-run
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--connection-string', help='Full PostgreSQL connection string')
    group.add_argument('--project-ref', help='Supabase project reference (e.g., xyzabc123)')
    
    parser.add_argument('--password', help='Database password (required with --project-ref)')
    parser.add_argument('--host', help='Database host (optional, auto-generated from project-ref)')
    parser.add_argument('--port', type=int, default=5432, help='Database port (default: 5432)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be deleted without actually deleting')
    
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
    
    # Get connection string if provided
    connection_string = args.connection_string if hasattr(args, 'connection_string') and args.connection_string else None
    
    print("="*70)
    print("🧹 LARGE GROUP CHAT CLEANUP")
    print("="*70)
    print(f"Supabase: {connection_params.get('host', 'connection string')}")
    if args.dry_run:
        print("Mode: DRY RUN (no changes will be made)")
    print("="*70)
    
    cleanup = None
    try:
        cleanup = LargeGroupCleanup(connection_params, connection_string)
        cleanup.connect()
        cleanup.cleanup(dry_run=args.dry_run)
        
        print("\n" + "="*70)
        print("✅ CLEANUP COMPLETE!")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ Cleanup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        if cleanup:
            cleanup.close()


if __name__ == '__main__':
    main()

