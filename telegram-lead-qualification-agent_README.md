# AI Lead Qualification Agent

Telegram-based AI agent that collects and qualifies business leads through a guided conversation.

## What problem it solves

Many small businesses receive messy messages from potential clients: incomplete requests, no budget, no timeline, no clear need, and no contact details.  
This agent helps collect the missing information, score the lead, and prepare a short sales brief for a human manager.

## Main features

- Lead intake through Telegram
- Natural conversation with a potential client
- Extracts key lead data:
  - name
  - email
  - phone
  - company
  - need
  - service type
  - budget
  - timeline
  - decision-maker status
- Lead score from 0 to 100
- Lead quality: weak / medium / strong
- Sales brief generation
- Lead status tracking
- CSV export
- PostgreSQL database
- Optional private access with `ALLOWED_CHAT_IDS`

## Example use case

A potential client writes:

> Hi, I need a website for a dental clinic. My budget is around 2000 EUR and I want to launch it next month.

The agent asks follow-up questions, extracts the lead details, scores the lead, and creates a sales summary.

## Commands

```text
/start — start the bot
/newlead — create a new lead
/leads — show all leads
/lead ID — show lead details
/brief ID — generate sales brief
/status ID status — update lead status
/report — show lead statistics
/export — export leads to CSV
/clear — clear all data
/myid — show Telegram chat ID
```

## Lead statuses

```text
new
collecting
qualified
contacted
won
lost
```

## Tech stack

- Python
- python-telegram-bot
- Groq API
- PostgreSQL
- Railway-compatible deployment

## Environment variables

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GROQ_API_KEY=your_groq_api_key
DATABASE_URL=your_postgres_database_url
ALLOWED_CHAT_IDS=
```

`ALLOWED_CHAT_IDS` is optional. If empty, the bot is open to everyone.

## How to run locally

```bash
pip install -r requirements.txt
python main.py
```

## How to deploy

The project includes a `Procfile`:

```text
worker: python main.py
```

It can be deployed to Railway or any service that supports Python workers.

## Portfolio value

This project demonstrates:

- AI lead qualification
- structured data extraction
- sales workflow automation
- CRM-like status tracking
- Telegram bot development
- database integration
- AI-generated sales summaries
