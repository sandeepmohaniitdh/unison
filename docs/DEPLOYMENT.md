# Running Unison for real

How to use real keys without putting them on GitHub, how Google sign-in works, and how to run Unison on a public server.

## 1. Private keys stay in `.env`

Every secret (Gemini key, Google client secret, passwords) goes in a file called `.env` in the repository folder, next to `docker-compose.yml`.

- `docker compose` reads `.env` by itself and passes the values to the containers.
- `.env` (and `.env.anything`) is in `.gitignore`, so `git add .` never picks it up. Only `.env.example`, which has no real values, is in Git.
- Never put a real key in `docker-compose.yml`, in code, in a screenshot or in a chat. If a key ever reaches GitHub, delete it at its provider at once and make a new one: removing the commit is not enough.

Start from the example:

    cp .env.example .env

Check that Git ignores it (the command prints the matching `.gitignore` line):

    git check-ignore -v .env

Each teammate makes their own `.env`. Share keys privately (or let each member make their own), never through the repository.

## 2. A real Gemini key

1. Open https://aistudio.google.com/apikey, sign in, and create an API key.
2. In `.env`:

       AI_PROVIDER=gemini
       GEMINI_API_KEY=your-key-here

3. Restart: `docker compose up -d`. The "AI feedback draft" button on the review page now asks Gemini.

Without a key, `AI_PROVIDER=fake` gives pretend suggestions for testing. The feature sends only the text of the PDF report, after names, emails and roll numbers are removed. Check Google's current terms: on the free tier Google may use what is sent to improve its products.

## 3. Google sign-in

### How it works

Unison uses Google's OpenID Connect "authorisation code flow with PKCE" (`backend/app/modules/auth/google.py`). The browser never sees a Google token; only the backend talks to Google.

1. The user clicks **Continue with Google**. The browser opens `/api/v1/auth/google`.
2. The backend makes three random values (a `state`, a `nonce` and a PKCE `verifier`), keeps them in a signed cookie that lasts 10 minutes, and sends the browser to Google's sign-in page.
3. The user picks their Google account. Google sends the browser back to `/api/v1/auth/google/callback` with a one-time `code` and the `state`.
4. The backend checks that the `state` matches its cookie (this stops forged sign-ins). It then sends the `code`, the `verifier` and the client secret straight to Google and gets back an ID token.
5. It checks the ID token: Google's signature (using Google's public keys), that it was made for our client ID, that it has not expired, and that the `nonce` matches.
6. It finds the account:
   - first by the Google account ID;
   - otherwise by the verified email (and links Google to that account);
   - otherwise it creates a new **student**, but only for an `@iitdh.ac.in` email (the "allowed email domain" setting).
7. It starts the same session as a password login (an HttpOnly cookie) and sends the user to their page.

Suspended and deleted accounts are refused. A Google account whose email Google has not verified is refused.

### Setting it up

1. Open https://console.cloud.google.com and create a project, for example "Unison".
2. Open **Google Auth Platform** (in older consoles: "APIs and Services", then "OAuth consent screen"):
   - **Branding:** app name "Unison", support email, and the logo if you like.
   - **Audience:** External. While the app is in "Testing", add the team's emails as test users. Publish it when the site is public.
   - **Data access:** the scopes `openid`, `email` and `profile` are enough.
3. **Clients**, then **Create client**, then **Web application**. Under "Authorized redirect URIs" add:
   - `http://localhost:8080/api/v1/auth/google/callback` (your laptop);
   - `https://your-domain/api/v1/auth/google/callback` (the real server, later).

   The address must match exactly, including `http` or `https` and the port.
4. Copy the client ID and secret into `.env`:

       GOOGLE_CLIENT_ID=...apps.googleusercontent.com
       GOOGLE_CLIENT_SECRET=...

5. Restart with `docker compose up -d`, open http://localhost:8080/login and click **Continue with Google**.

## 4. A public server

### What changes from the laptop

| On a laptop | On a real server |
|---|---|
| `AUTH_MODE=demo`: anyone can log in as anyone with a header | `AUTH_MODE=session`: only real logins |
| http://localhost:8080 | `https://your-domain`, with a free certificate from Let's Encrypt through Caddy |
| Mailpit catches every email | A mail service (Brevo, SendGrid, Mailgun or Gmail) sends real emails |
| Demo data from the seed | `SEED_ON_START=false`: an empty site with one admin |
| Default passwords (`unison`, `root`, `unison-admin`) | Your own long passwords and a random `SECRET_KEY` |
| MySQL, the API, Mailpit and phpMyAdmin reachable on ports 3307, 8000, 8025 and 8081 | Only ports 80 and 443 open, all through Caddy |

With `APP_ENV=production` the backend, worker and init refuse to start, and say why, if any laptop default is still set.

### Steps

1. **A server:** any Linux virtual machine with at least 2 GB of memory, with Docker and Git installed, for example from a cloud provider or the institute.
2. **A domain:** point a name such as `unison.example.org` at the server's address (a DNS "A" record). Open ports 80 and 443 in the firewall, plus SSH for you.
3. **Code and settings:**

       git clone https://github.com/sandeepmohaniitdh/unison.git
       cd unison
       cp .env.example .env
       nano .env

   Fill in the "real server" section: remove the `#` in front of each line and set the values. Make the secret key with:

       python3 -c "import secrets; print(secrets.token_urlsafe(48))"

   Use only letters and numbers in `MYSQL_PASSWORD`, because it is part of a database address. Set the database passwords before the first start: MySQL reads them only when its volume is created.
4. **Email:** create an account at a mail service, add your domain there, and add the DNS records it asks for (SPF and DKIM), so emails do not land in spam. Put its SMTP host, port, user and password in `.env`.
5. **Google:** add `https://your-domain/api/v1/auth/google/callback` to the OAuth client (section 3).
6. **Start:**

       docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

   Caddy gets the HTTPS certificate on the first visit. Open `https://your-domain`, log in as `ADMIN_EMAIL` with `ADMIN_PASSWORD`, and choose a new password. Then create departments, invite teachers and add courses from the admin console.

### Keeping it running

- **Logs:** `docker compose logs -f backend worker`
- **Update to a new version:**

      git pull
      docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

  Migrations run by themselves in `init`.
- **Back up** the database and the uploaded files every day, and keep copies off the server:

      docker compose exec db sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" unison' > unison-$(date +%F).sql
      docker run --rm -v unison_uploads:/data -v "$PWD":/backup alpine tar czf /backup/uploads-$(date +%F).tgz -C /data .

  Try a restore once, on a test machine, so you know it works.
- **Admin console, Settings:** check the allowed email domain and the limits.
- **Looking at the database:** phpMyAdmin does not start on the server. When you need it, start it for a while; it listens only on the server itself, and you reach it through an SSH tunnel from your laptop:

      docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile local-only up -d phpmyadmin
      # on your laptop:
      ssh -L 8081:127.0.0.1:8081 you@your-server
      # open http://localhost:8081, log in with unison and MYSQL_PASSWORD; afterwards:
      docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile local-only stop phpmyadmin

### Still to do before many people use it

- **Load test:** check the server with many users at the same time.
- **Automatic backups:** run the two backup commands above from a scheduled job (cron).
- **More than one server:** uploads are files in one Docker volume. To run on several servers, move them to shared or object storage first.
- **Privacy notice:** have the institute review the About page text for DPDP before real students sign up.
