# UK evening digest

NewsLens can send a short AI summary to a private Telegram chat around 7:07 pm UK
time. GitHub Actions can delay scheduled runs. The workflow checks UK daylight
saving time and skips the unused UTC slot. It takes up to 24 UK articles from
the past 24 hours, rotating through publishers, and makes one OpenAI request
with a limit of 900 output tokens. OpenAI may charge for input and output.
The digest includes source links. Publisher labels are context for comparing
coverage when articles overlap. The model can make mistakes, so check the
linked reporting for important claims.

Create a Telegram bot with BotFather and start a private chat with it, or add
it to a private group. Get the numeric chat ID from your own bot's updates.
Create a dedicated OpenAI project key for the digest.

Add these values under **Settings → Secrets and variables → Actions → Secrets**
in the repository:

| Repository secret | Value |
| --- | --- |
| `NEWSLENS_DIGEST_OPENAI_KEY` | OpenAI project API key |
| `NEWSLENS_DIGEST_TELEGRAM_TOKEN` | Telegram bot token |
| `NEWSLENS_DIGEST_CHAT_ID` | Numeric Telegram chat ID |

Use **Actions → UK evening news digest → Run workflow**. Leave **send** off to
check that the published dataset has eligible articles. Turn **send** on for one
real delivery test. A manual send can deliver another message for the same day.
After the test reaches the intended chat, add the repository variable
`ENABLE_EVENING_DIGEST` with the value `true` under the adjacent **Variables**
tab. Remove that variable to pause scheduled sends.

The job writes only generic status messages to Actions logs. Headlines and
excerpts go to OpenAI, and the rendered digest goes to the configured chat.
Generated text is checked against the supplied citation IDs. The workflow has
read-only repository access and saves no digest or delivery credentials to Git.
