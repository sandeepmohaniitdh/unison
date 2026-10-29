# AI usage

The course asks every team to say which AI tools they used, for which parts, and to give an example where the assistant was wrong and how it was caught. This file is kept up to date with each milestone.

## Tools

| Tool | Used for |
|---|---|
| Claude (Anthropic), in the Claude app | Drafting and revising the MS-1 design document; the ER diagram scripts and PDFs (MS-2); building the Figma screens through the Figma connector and small Figma plugins (MS-2); the backend code, migrations, seed script, tests, CI workflow and API documentation (MS-3) |
| The Gemini API (optional) | The product's own AI feature: rubric-based feedback drafts for teachers (see the design document, section 4) |

## How we used it

- Every piece of generated code was committed by the module's owner (see the README's ownership table), who read it, ran it and is responsible for explaining it in the viva.
- Generated code was only accepted with tests. The backend test suite runs against a real MySQL database in CI.
- The assistant never had push access: all commits and pull requests were made by team members.

## When the assistant was wrong

1. **Catalogue search found nothing in the tests.** The first version searched course codes and titles only with MySQL's FULLTEXT index. The tests failed: InnoDB's FULLTEXT index does not see rows until their transaction commits, and every test runs inside one rolled-back transaction. It would also have missed partial codes such as "CS3". Caught by the failing test `test_catalogue_is_public_with_search_and_filters`; fixed by combining FULLTEXT with `LIKE` (`app/modules/courses/service.py`, `_search_condition`).
2. **The pagination helper returned the wrong objects.** It decided whether to unwrap rows by counting selected columns, so `select(User)` returned rows instead of `User` objects and the admin user list crashed. Caught by `test_pagination_shape_and_limits`; fixed by checking `column_descriptions` instead (`app/core/pagination.py`).
3. **A conflict error crashed with a 500.** The `409 FINAL_CHANGED` error put the current final, with Python datetimes, into the error details, which could not be turned into JSON. Caught by `test_submit_final_replace_and_conflicts`; fixed by encoding error details safely and returning the final in the same IST format as everywhere else.
4. **The first `team_members` design broke third normal form.** It used a generated column to enforce one team per student per assignment. This was noticed while writing the 3NF section of the ER document; the table now uses the primary key (`assignment_id`, `user_id`) and a composite foreign key to `teams`.

TODO for the team: check that each example above is described as it happened, and add any you noticed yourselves.
