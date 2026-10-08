# Live GitHub test kit

The first end-to-end test of advisory mode against real GitHub (Phase 11's pending item). It
checks the connection (webhook → queue → worker → check → dashboard), not accuracy. The expected
verdicts below were produced by running the same code and comments through the tool offline
first, so a different verdict in the live check points to a connection problem, not a rule
problem.

Everything is done in the GitHub website; no `git` commands are needed.

## 0. Before you start

1. The system is running: `docker compose --profile advisory up -d --build`.
2. The webhook relay is running in its own terminal window, and stays open during the test:

   ```bash
   npx smee-client --url https://smee.io/YOUR-CHANNEL --target http://localhost:8000/github/webhook
   ```

   (Use the smee URL you gave the GitHub App. The first run asks to install `smee-client`: answer `y`.)
3. Optional: watch the worker in another window: `docker compose logs -f worker`.

## 1. Create the pull request

1. In the test repository, click **Add file → Create new file**.
2. File name: `shop/accounts.py`. Paste exactly this:

   ```python
   def create_user(db, username, email):
       db.insert("users", {"username": username, "email": email})
       return {"status": "created"}


   def get_discount(price, percent):
       return price - price * percent / 100


   def load_config(path):
       with open(path) as f:
           return f.read()


   def delete_user(db, user_id):
       db.delete("users", user_id)
       return {"status": "deleted"}


   def total(items):
       t = 0
       for i in items:
           t = t + i["price"]
       return t
   ```

3. Click **Commit changes…**, choose **"Create a new branch for this commit and start a pull
   request"**, then **Propose changes** → **Create pull request**.

## 2. Leave five review comments

Open the pull request → **Files changed**. Hover a line, click the blue **+**, write the comment,
then click **Add single comment** (not "Start a review").

| # | Line | Comment to write |
|---|---|---|
| T1 | 2 `db.insert(...)` | ``Please validate that `username` is not empty before inserting it.`` |
| T2 | 11 `with open(path) as f:` | `Please handle the case where the file does not exist (FileNotFoundError).` |
| T3 | 7 `return price - price * percent / 100` | ``Please validate that `percent` is between 0 and 100, and add a test for get_discount.`` |
| T4 | 22 `for i in items:` | `This could be cleaner.` |
| T5 | 17 `return {"status": "deleted"}` | a suggestion only (see below) |

For T5, don't type any sentence. Click the **±** ("Insert a suggestion") button in the comment
toolbar. The box then contains exactly this, and you only edit the middle line:

````text
```suggestion
    return {"status": "deleted", "id": user_id}
```
````

Any extra sentence in the comment counts as a separate request that the tool can't verify, which
makes the whole thread "uncertain".

## 3. Make the fixes

1. On the T5 comment, click **Commit suggestion** → **Commit changes**.
2. In **Files changed**, open the **⋯** menu on `shop/accounts.py` → **Edit file**, and change
   the first two functions to:

   ```python
   def create_user(db, username, email):
       if not username:
           raise ValueError("username is required")
       db.insert("users", {"username": username, "email": email})
       return {"status": "created"}


   def get_discount(price, percent):
       if percent < 0 or percent > 100:
           raise ValueError("percent must be between 0 and 100")
       return price - price * percent / 100
   ```

   Leave `load_config` and `total` unchanged (T2 and T4 are deliberately not fixed). Commit to the
   same branch.

## 4. Resolve the threads

Open the **Conversation** tab and click **Resolve conversation** on all five comments, **after**
the fixes are committed. Each resolve sends one event; the worker verifies that thread.

## 5. What should happen

Within a few seconds of each resolve, a check named **VeriReview** appears on the pull request
(**Checks** tab), with a neutral (grey) result. It lists every resolved thread:

| # | Expected verdict | Why |
|---|---|---|
| T1 | SATISFIED | a real check on `username` before the insert |
| T2 | NOT_SATISFIED | nothing changed |
| T3 | PARTIALLY_SATISFIED | range check added, but no test |
| T4 | UNCERTAIN | the request is too vague to verify |
| T5 | SATISFIED | the suggestion was committed as written |

Then:

6. **Re-run:** press **Re-run** on the VeriReview check (Checks tab, or the check's
   **Details** page). The check is re-created on the pull request's latest commit, covering every
   resolved thread. Note: the check stays on the commit where threads were resolved; after you push
   new commits, the latest commit has no VeriReview check (so no Re-run button there). Find it via
   the **Commits** tab → the status icon next to the older commit → **Details** → **Re-run**.
7. **Dashboard:** open http://localhost:8000/dashboard: the test repository appears with the
   pull request and each thread, its evidence, code and diff.
8. **Forged message:** already checked: an unsigned request to the webhook is rejected with 401.

## If something doesn't appear

- Nothing at all: is the smee window still running and showing incoming events? Is the worker
  running (`docker compose --profile advisory ps`)?
- The smee window shows events but no check: look at `docker compose logs worker` and the
  dashboard's **Jobs** page (it shows each job's last error).
- A different verdict than the table: note it. That points to a difference between live GitHub
  data and the offline cases, which is exactly what this test is for.
