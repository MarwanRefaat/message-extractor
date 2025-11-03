# Email Import Guide

This guide explains how to import emails into the SQL database using the LLM-based email extractor.

## Overview

The email import system uses a local LLM (GPT4All) to intelligently parse emails from various sources and import them into the unified database structure. It handles:

- ✅ EML files (from gmail-exporter or other tools)
- ✅ JSON/JSONL email exports
- ✅ Raw email text files
- ✅ Email threads and conversation grouping
- ✅ CC/BCC recipients
- ✅ Attachments
- ✅ HTML to plain text conversion
- ✅ Signature removal
- ✅ Quoted text cleanup

## Prerequisites

1. **Install GPT4All** (if not already installed):
   ```bash
   pip install gpt4all
   ```

2. **Ensure database exists**: The script will use the existing database at `data/database/chats.db` or create it if needed.

## Usage

### Import from EML Directory (Recommended)

If you've used `gmail-exporter` to export your emails as EML files:

```bash
python scripts/import_emails.py --db data/database/chats.db --eml-dir gmail_export/messages
```

### Import from Single File

```bash
# EML file
python scripts/import_emails.py --db data/database/chats.db --file path/to/email.eml

# JSON/JSONL file
python scripts/import_emails.py --db data/database/chats.db --file path/to/emails.jsonl
```

### Import from Directory

```bash
# Import all email files from a directory
python scripts/import_emails.py --db data/database/chats.db --directory path/to/emails/

# Limit number of files processed
python scripts/import_emails.py --db data/database/chats.db --directory path/to/emails/ --max-files 1000
```

### Import from JSON/JSONL File

```bash
python scripts/import_emails.py --db data/database/chats.db --json-file path/to/emails.jsonl
```

## How It Works

### 1. LLM-Based Extraction

The `EmailLLMExtractor` uses a local LLM to intelligently parse emails:

- **Structured extraction**: Parses headers, body, recipients, timestamps
- **Smart cleaning**: Removes HTML, signatures, quoted text
- **Thread detection**: Identifies email threads using In-Reply-To and References headers
- **Fallback parsing**: Uses rule-based parsing if LLM is unavailable

### 2. Database Import

The `EmailDatabaseImporter`:

- **Creates conversations**: Groups emails by thread or subject+participants
- **Links contacts**: Creates/updates contact records, cross-links with existing contacts
- **Handles threads**: Properly links replies to original messages
- **Detects groups**: Identifies group conversations (3+ participants)
- **Preserves metadata**: Stores attachments, timestamps, and raw data

## Features

### Email Cleaning

The extractor automatically:

- Converts HTML emails to plain text
- Removes email signatures (content after "--")
- Removes quoted/replied text
- Handles multipart messages (plain text + HTML)
- Preserves important formatting (paragraphs, lists)

### Thread Handling

Emails are automatically grouped into conversations based on:

1. `thread_id` from References header (if available)
2. Subject line + participant list (as fallback)

Replies are linked to original messages using `reply_to_message_id`.

### Contact Management

- **Cross-platform linking**: Email contacts are linked with existing contacts by email address
- **Contact merging**: If a contact exists on another platform (e.g., WhatsApp) with the same email, they're linked
- **"Me" detection**: Automatically detects your email addresses if you have a contact marked as "me"

## Example Workflow

### Step 1: Export Emails

```bash
# Using gmail-exporter (if you have it set up)
cd tools/gmail-exporter
./gmail-exporter export --save-eml --eml-dir messages INBOX SENT
```

### Step 2: Import to Database

```bash
# Import all EML files
python scripts/import_emails.py \
  --db data/database/chats.db \
  --eml-dir tools/gmail-exporter/messages
```

### Step 3: Verify Import

```bash
# Check the database
sqlite3 data/database/chats.db "SELECT COUNT(*) FROM messages WHERE platform = 'email';"
sqlite3 data/database/chats.db "SELECT COUNT(*) FROM conversations WHERE platform = 'email';"
```

## Command Line Options

```
--db PATH              Path to SQLite database (default: data/database/chats.db)
--file PATH            Import from a single email file
--directory PATH       Import from directory containing email files
--eml-dir PATH         Import from directory containing EML files
--json-file PATH       Import from JSON/JSONL file
--max-files N          Maximum number of files to process
```

## Troubleshooting

### LLM Not Available

If GPT4All is not installed, the extractor will fall back to rule-based parsing. This works well for EML files but may be less accurate for unstructured data.

```bash
pip install gpt4all
```

### Memory Issues with Large Datasets

If processing many emails causes memory issues, process in batches:

```bash
# Process first 1000 files
python scripts/import_emails.py --directory emails/ --max-files 1000

# Then continue with next batch by moving processed files
```

### Duplicate Messages

The import script automatically skips duplicate messages based on `platform_message_id`. If you need to re-import:

1. The script will skip duplicates automatically
2. Or you can delete existing email messages: `DELETE FROM messages WHERE platform = 'email';`

## Integration with Other Platforms

Emails are stored in the same unified database structure as other platforms:

- **Contacts**: Shared contact table (linked by email/phone)
- **Conversations**: Each email thread is a conversation
- **Messages**: Individual emails are stored as messages
- **Cross-platform queries**: Query across all platforms using the same schema

Example query to see all conversations with a specific person:

```sql
SELECT m.*, c.conversation_name 
FROM messages m
JOIN conversations c ON m.conversation_id = c.conversation_id
JOIN contacts co ON m.sender_id = co.contact_id
WHERE co.email = 'person@example.com'
ORDER BY m.timestamp DESC;
```

## Performance

- **LLM extraction**: ~1-5 seconds per email (depending on LLM model and email size)
- **Rule-based extraction**: ~0.1 seconds per email
- **Database import**: ~0.01 seconds per email

For large datasets (1000+ emails), expect:
- **With LLM**: ~1-2 hours for 1000 emails
- **Without LLM**: ~2-5 minutes for 1000 emails

## Best Practices

1. **Start small**: Test with a small directory first (10-50 emails)
2. **Use EML format**: EML files are most reliably parsed
3. **Check logs**: Review import logs for any warnings or errors
4. **Verify data**: After import, verify a sample of emails in the database
5. **Backup database**: Before large imports, backup your database

