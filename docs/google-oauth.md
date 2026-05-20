# Google OAuth Setup Notes

The MVP runs with `CD_GOOGLE_PROVIDER=mock` by default. Real Google access should replace the mock provider behind the existing backend interface.

## OAuth Mode

- Start with an external Google Cloud OAuth app in testing mode.
- Add pilot accounts as test users.
- Request `openid`, `email`, and `profile` for sign-in.
- Request Classroom and Drive scopes only when the user connects Classroom or starts an export.

## MVP Scopes

- `classroom.courses.readonly`
- `classroom.coursework.students.readonly`
- `classroom.student-submissions.students.readonly`
- `classroom.profile.emails`
- `drive.readonly`

`drive.readonly` is likely required for broad submission download access and can trigger Google verification for public launch. Keep the app in test-user mode until the pilot workflow is proven.
