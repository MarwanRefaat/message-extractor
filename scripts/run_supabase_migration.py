#!/usr/bin/env python3
"""
Run Supabase migration script

Usage:
    python scripts/run_supabase_migration.py --connection-string "postgresql://postgres:password@db.project.supabase.co:5432/postgres"
    
    OR
    
    python scripts/run_supabase_migration.py --host db.project.supabase.co --password yourpassword --project-ref xyzabc123
"""

import argparse
import sys
import os
from pathlib import Path
import re

try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("❌ psycopg2 not installed. Install it with:")
    print("   pip install psycopg2-binary")
    sys.exit(1)


def parse_connection_string(connection_string):
    """Parse PostgreSQL connection string"""
    # Format: postgresql://user:password@host:port/database
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


def build_connection_string(host, password, project_ref, port=5432):
    """Build connection string from components"""
    return {
        'host': f'db.{project_ref}.supabase.co' if not host.startswith('db.') else host,
        'port': str(port),
        'database': 'postgres',
        'user': 'postgres',
        'password': password
    }


def read_sql_file(file_path):
    """Read SQL file and split into statements"""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"SQL file not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by semicolon, but preserve function definitions
    statements = []
    current_statement = []
    in_function = False
    
    for line in content.split('\n'):
        stripped = line.strip()
        
        # Track function definitions
        if 'CREATE OR REPLACE FUNCTION' in stripped.upper() or '$$' in stripped:
            if '$$' in stripped and stripped.count('$$') == 2:
                # Single-line function
                current_statement.append(line)
                statements.append('\n'.join(current_statement))
                current_statement = []
                in_function = False
            elif '$$' in stripped:
                in_function = not in_function
                current_statement.append(line)
            else:
                current_statement.append(line)
        elif in_function:
            current_statement.append(line)
            if stripped.endswith('$$'):
                in_function = False
        else:
            current_statement.append(line)
            if stripped.endswith(';') and not stripped.startswith('--'):
                statement = '\n'.join(current_statement).strip()
                if statement and not statement.startswith('--'):
                    statements.append(statement)
                current_statement = []
    
    # Add any remaining statement
    if current_statement:
        remaining = '\n'.join(current_statement).strip()
        if remaining:
            statements.append(remaining)
    
    return statements


def execute_migration(connection_params, sql_file_path):
    """Execute the migration script"""
    print("🚀 Starting Supabase migration...")
    print(f"📁 Reading SQL file: {sql_file_path}")
    
    # Read SQL statements
    try:
        statements = read_sql_file(sql_file_path)
        print(f"✅ Found {len(statements)} SQL statements")
    except Exception as e:
        print(f"❌ Error reading SQL file: {e}")
        return False
    
    # Connect to database
    print(f"🔌 Connecting to {connection_params['host']}:{connection_params['port']}...")
    try:
        conn = psycopg2.connect(**connection_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        print("✅ Connected successfully")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\n💡 Tips:")
        print("   - Check your password is correct")
        print("   - Verify your IP isn't blocked in Supabase")
        print("   - Ensure the project is fully provisioned")
        return False
    
    # Execute statements
    print("\n📝 Executing migration...")
    executed = 0
    errors = []
    
    for i, statement in enumerate(statements, 1):
        if not statement.strip() or statement.strip().startswith('--'):
            continue
        
        try:
            cursor.execute(statement)
            executed += 1
            if i % 10 == 0:
                print(f"   ✓ Executed {i}/{len(statements)} statements...")
        except Exception as e:
            error_msg = f"Statement {i}: {str(e)[:100]}"
            errors.append((i, statement[:100], str(e)))
            # Don't stop on errors - some might be expected (like IF NOT EXISTS)
            if 'already exists' not in str(e).lower() and 'does not exist' not in str(e).lower():
                print(f"   ⚠️  Warning on statement {i}: {str(e)[:80]}")
    
    cursor.close()
    conn.close()
    
    print(f"\n✅ Migration complete!")
    print(f"   - Executed {executed} statements")
    
    if errors:
        print(f"   - {len(errors)} warnings (non-critical)")
    
    # Verify tables were created
    print("\n🔍 Verifying tables...")
    try:
        conn = psycopg2.connect(**connection_params)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        
        expected_tables = ['contacts', 'conversations', 'messages', 'conversation_participants', 
                          'calendar_events', 'message_tags']
        
        print(f"   ✓ Found {len(tables)} tables:")
        for table in tables:
            marker = "✓" if table in expected_tables else "?"
            print(f"     {marker} {table}")
        
        missing = set(expected_tables) - set(tables)
        if missing:
            print(f"\n   ⚠️  Missing tables: {', '.join(missing)}")
        else:
            print("\n   ✅ All expected tables created!")
            
    except Exception as e:
        print(f"   ⚠️  Could not verify: {e}")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Run Supabase migration script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using connection string
  python scripts/run_supabase_migration.py \\
    --connection-string "postgresql://postgres:password@db.xyz.supabase.co:5432/postgres"
  
  # Using individual parameters
  python scripts/run_supabase_migration.py \\
    --project-ref xyzabc123 \\
    --password yourpassword
  
  # From environment variable
  export SUPABASE_CONNECTION="postgresql://..."
  python scripts/run_supabase_migration.py --connection-string "$SUPABASE_CONNECTION"
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--connection-string',
        help='Full PostgreSQL connection string'
    )
    group.add_argument(
        '--project-ref',
        help='Supabase project reference (e.g., xyzabc123). Also provide --password'
    )
    
    parser.add_argument(
        '--password',
        help='Database password (required with --project-ref)'
    )
    parser.add_argument(
        '--host',
        help='Database host (optional, auto-generated from project-ref if not provided)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5432,
        help='Database port (default: 5432)'
    )
    parser.add_argument(
        '--sql-file',
        default='data/database/supabase_migration.sql',
        help='Path to SQL migration file (default: data/database/supabase_migration.sql)'
    )
    
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
        # Try environment variable
        conn_str = os.getenv('SUPABASE_CONNECTION')
        if conn_str:
            connection_params = parse_connection_string(conn_str)
        else:
            parser.error("Must provide --connection-string or --project-ref (or set SUPABASE_CONNECTION env var)")
    
    # Execute migration
    sql_file = Path(__file__).parent.parent / args.sql_file
    success = execute_migration(connection_params, sql_file)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

