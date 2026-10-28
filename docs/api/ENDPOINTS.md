# Unison API: every endpoint

Generated from the code by `backend/scripts/export_openapi.py`; do not edit by hand.
The full description (bodies, responses, errors) is in [docs/openapi.yaml](../openapi.yaml).

105 operations under `/api/v1`.

## auth

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/auth/config` | Login options for the sign-in page |
| POST | `/api/v1/auth/register` | Register: create a student account and log in |
| POST | `/api/v1/auth/login` | Log in with email and password |
| POST | `/api/v1/auth/logout` | Log out (ends this session) |
| POST | `/api/v1/auth/email-verifications` | Confirm an email with the token from its link |
| POST | `/api/v1/auth/password-reset-requests` | Email a password reset link |
| POST | `/api/v1/auth/password-resets` | Choose a new password from the emailed link |
| GET | `/api/v1/auth/google` | Start Google sign-in (redirects to Google) |
| GET | `/api/v1/auth/google/callback` | Google redirects back here |

## users

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/users/me` | The logged-in user |
| PATCH | `/api/v1/users/me` | Edit the profile |
| PUT | `/api/v1/users/me/password` | Set or change the password |
| POST | `/api/v1/users/me/emails` | Add a second email |
| PATCH | `/api/v1/users/me/emails/{email_id}` | Make a verified email the primary one |
| DELETE | `/api/v1/users/me/emails/{email_id}` | Remove a second email |
| POST | `/api/v1/users/me/emails/{email_id}/verifications` | Send the verification link again |
| DELETE | `/api/v1/users/me/google` | Unlink the Google account |
| GET | `/api/v1/users/me/personal-data` | Download my data (JSON) |
| GET | `/api/v1/users/me/deletion` | What deleting the account would leave |
| POST | `/api/v1/users/me/deletion` | Delete my account |

## courses

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/departments` | List departments (public) |
| POST | `/api/v1/departments` | Create a department (admins) |
| PATCH | `/api/v1/departments/{department_id}` | Rename a department (admins) |
| GET | `/api/v1/courses` | Course catalogue (public) |
| POST | `/api/v1/courses` | Create a course |
| GET | `/api/v1/users/me/courses` | My courses (taught or enrolled) |
| GET | `/api/v1/courses/{course_id}` | Get one course (public) |
| PATCH | `/api/v1/courses/{course_id}` | Edit or archive a course |
| GET | `/api/v1/courses/{course_id}/members` | List course members |
| POST | `/api/v1/courses/{course_id}/teachers` | Assign a teacher (admins) |
| PATCH | `/api/v1/courses/{course_id}/members/{user_id}` | Re-enrol a removed student |
| DELETE | `/api/v1/courses/{course_id}/members/{user_id}` | Remove a member |
| GET | `/api/v1/courses/{course_id}/join-requests` | List pending join requests |
| POST | `/api/v1/courses/{course_id}/join-requests` | Ask to join a course |
| DELETE | `/api/v1/courses/{course_id}/join-requests/mine` | Cancel my join request |
| PATCH | `/api/v1/courses/{course_id}/join-requests/{request_id}` | Approve or reject a join request |

## invitations

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/courses/{course_id}/invitations` | List a course's invitations |
| POST | `/api/v1/courses/{course_id}/invitations` | Invite students (or a co-teacher) by email |
| GET | `/api/v1/teams/{team_id}/invitations` | List the team's invitations |
| POST | `/api/v1/teams/{team_id}/invitations` | Invite a classmate to the team |
| GET | `/api/v1/admin/staff-invitations` | List staff invitations |
| POST | `/api/v1/admin/staff-invitations` | Invite a teacher or admin |
| PATCH | `/api/v1/invitations/{invitation_id}` | Accept or decline an invitation (invitee) |
| DELETE | `/api/v1/invitations/{invitation_id}` | Cancel a pending invitation (sender) |
| GET | `/api/v1/users/me/invitations` | List my pending invitations |
| GET | `/api/v1/invitation-links/{token}` | Open an invitation link |
| PATCH | `/api/v1/invitation-links/{token}` | Accept or decline from the emailed link |

## resources

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/courses/{course_id}/resources` | A course's resources |
| POST | `/api/v1/courses/{course_id}/resources/files` | Upload a file resource (draft) |
| POST | `/api/v1/courses/{course_id}/resources/links` | Add a link resource (draft) |
| POST | `/api/v1/courses/{course_id}/resource-publications` | Publish one or several resources |
| PATCH | `/api/v1/resources/{resource_id}` | Edit a resource |
| DELETE | `/api/v1/resources/{resource_id}` | Delete a resource |
| GET | `/api/v1/resources/{resource_id}/content` | Download a file resource's content |

## assignments

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/courses/{course_id}/assignments` | A course's assignments |
| POST | `/api/v1/courses/{course_id}/assignments` | Create an assignment (as a draft) |
| GET | `/api/v1/assignments/{assignment_id}` | One assignment with its rubric |
| PATCH | `/api/v1/assignments/{assignment_id}` | Edit, publish, extend or lock an assignment |
| DELETE | `/api/v1/assignments/{assignment_id}` | Delete a draft assignment |

## teams

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/assignments/{assignment_id}/teams` | All teams (teachers) |
| POST | `/api/v1/assignments/{assignment_id}/teams` | Create a team (students, group assignments) |
| GET | `/api/v1/assignments/{assignment_id}/my-team` | My team for this assignment |
| GET | `/api/v1/teams/{team_id}` | One team (members and teachers) |
| PATCH | `/api/v1/teams/{team_id}` | Rename the team |
| DELETE | `/api/v1/teams/{team_id}/members/me` | Leave the team (before its first final) |
| PATCH | `/api/v1/teams/{team_id}/members/{user_id}` | Move a member to another team (teachers) |
| DELETE | `/api/v1/teams/{team_id}/members/{user_id}` | Remove a member (teachers) |

## submissions

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/teams/{team_id}/submission` | The team's submission state |
| GET | `/api/v1/teams/{team_id}/submission/drafts` | The team's drafts |
| POST | `/api/v1/teams/{team_id}/submission/drafts` | Upload a draft |
| GET | `/api/v1/teams/{team_id}/submission/finals` | Every final, including replaced ones |
| POST | `/api/v1/teams/{team_id}/submission/finals` | Submit a draft as the team's final |
| GET | `/api/v1/submission-files/{file_id}/content` | Download a submitted file |

## reviews

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/assignments/{assignment_id}/reviews` | Every team's state and mark (review page) |
| PATCH | `/api/v1/assignments/{assignment_id}/reviews` | Release every complete review of the assignment |
| GET | `/api/v1/teams/{team_id}/review` | Review sheet for the team's final |
| PUT | `/api/v1/teams/{team_id}/review` | Save scores and comments |
| PATCH | `/api/v1/teams/{team_id}/review` | Release this team's marks |
| PUT | `/api/v1/teams/{team_id}/review/adjustments/{user_id}` | Adjust one member's mark |
| DELETE | `/api/v1/teams/{team_id}/review/adjustments/{user_id}` | Remove an adjustment |
| GET | `/api/v1/teams/{team_id}/marks` | My released marks |

## ai

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/ai/status` | Is the AI feedback draft available? |
| GET | `/api/v1/teams/{team_id}/review/ai-drafts` | AI drafts for the team's current final |
| POST | `/api/v1/teams/{team_id}/review/ai-drafts` | Ask for an AI feedback draft for the team's final |
| POST | `/api/v1/assignments/{assignment_id}/ai-drafts` | Draft all: queue a draft for every final |
| GET | `/api/v1/ai-drafts/{draft_id}` | One AI draft (poll until ready) |

## notifications

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/notifications` | List my notifications, newest first |
| PATCH | `/api/v1/notifications` | Mark all my notifications as read |
| GET | `/api/v1/notifications/unread-count` | Number for the bell |
| PATCH | `/api/v1/notifications/{notification_id}` | Mark one notification as read |
| GET | `/api/v1/users/me/notification-preferences` | List my email switches |
| PUT | `/api/v1/users/me/notification-preferences` | Turn email types on or off |
| GET | `/api/v1/courses/{course_id}/notification-rules` | List the course's email rules |
| PUT | `/api/v1/courses/{course_id}/notification-rules` | Choose which events email members and teachers |
| GET | `/api/v1/dashboards/student` | Get the student dashboard |
| GET | `/api/v1/dashboards/teacher` | Get the teacher dashboard |

## admin

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/admin/stats` | Get platform statistics |
| GET | `/api/v1/admin/users` | Search users |
| GET | `/api/v1/admin/users/{user_id}` | Get one user with emails and courses |
| PATCH | `/api/v1/admin/users/{user_id}` | Change a user's role, or suspend or restore the account |
| GET | `/api/v1/admin/courses` | List all courses, or those without an active teacher |
| GET | `/api/v1/admin/audit-entries` | List the audit log, newest first |
| GET | `/api/v1/admin/settings` | List platform settings |
| PUT | `/api/v1/admin/settings/{key}` | Change a platform setting |

## health

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/health` | Is the API up? |
