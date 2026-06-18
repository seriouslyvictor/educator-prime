# Google permissions

Classroom Downloader uses incremental Google OAuth. The app asks for the
smallest capability needed for the action the teacher is taking, then stores and
reports the scopes Google actually granted.

| Capability | Asked when | Required scopes | If declined |
|---|---|---|---|
| `identity` | Initial sign-in | `openid`, `email`, `profile` | Stay on the connect screen |
| `classroom_read` | Opening the Classroom workspace | `classroom.courses.readonly`, `classroom.coursework.students.readonly` | Keep the Google session and show a Classroom permission action |
| `submissions_read` | Creating grading/export work for an activity | `classroom.student-submissions.students.readonly` | Keep course/activity browsing available |
| `student_profile_read` | Showing student names, emails, and photos from submissions | `classroom.profile.emails`, `classroom.profile.photos`, `classroom.rosters.readonly` | Use safe placeholders where possible |
| `drive_read` | Exporting/downloading or grading attached submission files | `drive.readonly` | Keep Classroom browsing available and block file-content actions |

## Source guidance

- Google OAuth web-server flow and incremental auth:
  https://developers.google.com/identity/protocols/oauth2/web-server
- Google granular permissions:
  https://developers.google.com/identity/protocols/oauth2/resources/granular-permissions
- Google OAuth policies:
  https://developers.google.com/identity/protocols/oauth2/policies
- Google API Services User Data Policy:
  https://developers.google.com/terms/api-services-user-data-policy
- Google Drive scope selection:
  https://developers.google.com/workspace/drive/api/guides/api-specific-auth
- Google Classroom scope list:
  https://developers.google.com/workspace/classroom/guides/auth

## Drive scope decision

The current export and grading flows automatically read Classroom submission
attachments. Those attachments are Drive files, so the app still needs
`https://www.googleapis.com/auth/drive.readonly` when the teacher chooses an
export, download, or grading action that reads file content.

`drive.readonly` is a restricted scope. It is intentionally requested only at
the file-content boundary, not at initial sign-in and not when merely browsing
Classroom courses and activities.

`drive.file` is deferred because it only covers files the user selected or
created through the app. It does not preserve the current automatic Classroom
attachment export unless a Google Picker or other user-selected-file workflow is
built first.

## Production readiness checklist

- OAuth consent screen lists only implemented scopes.
- Sensitive and restricted scopes are verified before public production use.
- Privacy policy and in-product disclosures match actual data access.
- Tokens stay encrypted at rest.
- Disconnect deletes local tokens; add Google token revocation when the app no
  longer needs access.
