# AI usage

The course asks every team to say which AI tools they used, for which parts, and to give an example where the assistant was wrong and how it was caught. This file is kept up to date with each milestone.

## Tools

| Tool | Used for |
|---|---|
| Claude (Anthropic), in the Claude app | Drafting and revising the MS-1 design document; the ER diagram scripts and PDFs (MS-2); building the Figma screens through the Figma connector and small Figma plugins (MS-2); the backend code, migrations, seed script, tests, CI workflow and API documentation (MS-3); the React pages, frontend tests, Docker and CI setup for the frontend (MS-4); the Playwright end-to-end tests and the AI evaluation set and script (MS-5); the final report and presentation drafts (MS-6) |
| The Gemini API (optional) | The product's own AI feature: rubric-based feedback drafts for teachers (see the design document, section 4) |

## How we used it

- Every piece of generated code was committed by a team member who read it, ran it and is responsible for explaining it in the viva: backend modules by their owners (see the README's ownership table), the MS-4 frontend by Sandeep M.
- Generated code was only accepted with tests. The backend test suite runs against a real MySQL database in CI; the frontend page tests click through the app against answers recorded from the seeded backend.
- The assistant never had push access: all commits and pull requests were made by team members.

## When the assistant was wrong

1. **Catalogue search found nothing in the tests.** The first version searched course codes and titles only with MySQL's FULLTEXT index. The tests failed: InnoDB's FULLTEXT index does not see rows until their transaction commits, and every test runs inside one rolled-back transaction. It would also have missed partial codes such as "CS3". Caught by the failing test `test_catalogue_is_public_with_search_and_filters`; fixed by combining FULLTEXT with `LIKE` (`app/modules/courses/service.py`, `_search_condition`).
2. **The pagination helper returned the wrong objects.** It decided whether to unwrap rows by counting selected columns, so `select(User)` returned rows instead of `User` objects and the admin user list crashed. Caught by `test_pagination_shape_and_limits`; fixed by checking `column_descriptions` instead (`app/core/pagination.py`).
3. **A conflict error crashed with a 500.** The `409 FINAL_CHANGED` error put the current final, with Python datetimes, into the error details, which could not be turned into JSON. Caught by `test_submit_final_replace_and_conflicts`; fixed by encoding error details safely and returning the final in the same IST format as everywhere else.
4. **The first `team_members` design broke third normal form.** It used a generated column to enforce one team per student per assignment. This was noticed while writing the 3NF section of the ER document; the table now uses the primary key (`assignment_id`, `user_id`) and a composite foreign key to `teams`.

5. **Git would have left out the frontend helpers.** The repository's `.gitignore` started from the standard Python template, whose `lib/` rule also matches `frontend/src/lib/` (dates, text helpers, dark mode). A fresh clone would have failed to build. Caught with `git check-ignore` before the first frontend commit; fixed with `!frontend/src/lib/` in `.gitignore`.
6. **The invitation page went blank.** The page read the invitation before it had loaded, in the moment between "not asked yet" and "loading". Caught while clicking through the page in a browser; fixed in `src/api/useApi.js` (data counts as loading until the answer for the current inputs arrives), and an error boundary now shows a message instead of a blank page.
7. **Pages scrolled sideways on phones.** Screen-reader-only table headings were positioned outside the page. Caught by a check that looks for anything wider than a 390 px screen; fixed by keeping those labels inside their table (`src/styles/base.css`, `components.css`).
8. **After "Log out", the next person landed on the previous user's page.** The login guard treated a deliberate log out like an expired session and kept the old page as `?next=`, so the next user to log in opened, for example, the previous user's profile. Caught by Sandeep while testing on his laptop; fixed in `src/auth/AuthContext.jsx` and `src/layouts/RequireAuth.jsx` (after "Log out" the login page has no `next`), with a page test that logs out and logs in as someone else.
9. **`npm run dev` did not work on Sandeep's laptop.** The likely cause: the Vite proxy pointed at `localhost:8000`, which Node on Windows can resolve to the IPv6 address first, where the backend is not listening. Fixed by using `127.0.0.1`, and the dev server now says "The backend is not answering" instead of a bare error (`vite.config.js`).
10. **The long-report evaluation case was not long.** The first version of case R01 repeated one page 20 times, about 6,500 characters, so it never reached the 12,000-character limit it was meant to test. Caught by the evaluation itself (the "truncated" check failed); fixed by repeating it 90 times (about 29,000 characters).
11. **An end-to-end test looked for students by name on the review page.** The test typed the student's name into the review page's search box, but that box only searches team names ("Individual 18"). Caught when the test failed; the test now opens the review page with the team in the address, as the teacher's notification link does. The search limitation is noted as future work.
12. **Two evaluation cases gave the model the wrong assignment.** The problem-set cases (Q09, Q10) were sent with the web-application project's description, so in the first live run Gemini marked a correct proof as off-topic (0/10) and Q10 passed only by accident. Caught by reading the first run's results (`docs/ai_evaluation_run1.md`); fixed by giving each rubric its own assignment description in `backend/evaluation/ai_cases.json`.

The same first run also found two real weaknesses in the AI feature, not mistakes by the assistant: a fake "SYSTEM:" line (I02) and a fake end of the report with a "note from the teacher" (I03) both got full marks. We now remove `<report>` tags written inside a report, flag those patterns to the teacher, and tell the model in the prompt (version 2) that such text is part of the student's work (`app/modules/ai/redact.py`, `service.py`).

TODO for the team: check that each example above is described as it happened, and add any you noticed yourselves.
