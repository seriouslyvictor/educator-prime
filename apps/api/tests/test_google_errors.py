from httplib2 import Response

from googleapiclient.errors import HttpError

from classroom_downloader.api.google_errors import google_api_http_exception


def test_classroom_account_type_403_maps_to_classroom_not_available() -> None:
    error = HttpError(
        Response({"status": "403", "reason": "Forbidden"}),
        b'{"error":{"message":"Classroom is not enabled for this account","errors":[{"reason":"forbidden","message":"Classroom is not enabled"}]}}',
    )

    result = google_api_http_exception(error)

    assert result is not None
    assert result.status_code == 403
    assert result.detail["code"] == "classroom_not_available"
