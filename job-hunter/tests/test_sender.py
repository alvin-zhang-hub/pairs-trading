from unittest.mock import patch, MagicMock

from mailer.sender import send_email


@patch("mailer.sender.smtplib.SMTP_SSL")
def test_send_email_calls_smtp(mock_smtp_class):
    mock_server = MagicMock()
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

    send_email(
        subject="Test Subject",
        html_body="<p>Hello</p>",
        to_addr="test@example.com",
        from_addr="sender@example.com",
        app_password="fake-password",
    )

    mock_smtp_class.assert_called_once_with("smtp.gmail.com", 465)
    mock_server.login.assert_called_once_with("sender@example.com", "fake-password")
    mock_server.send_message.assert_called_once()


@patch("mailer.sender.smtplib.SMTP_SSL")
def test_send_email_message_has_correct_subject(mock_smtp_class):
    mock_server = MagicMock()
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

    send_email(
        subject="Job Hunter Daily",
        html_body="<p>Jobs</p>",
        to_addr="test@example.com",
        from_addr="sender@example.com",
        app_password="fake-password",
    )

    sent_msg = mock_server.send_message.call_args[0][0]
    assert sent_msg["Subject"] == "Job Hunter Daily"
    assert sent_msg["To"] == "test@example.com"
    assert sent_msg["From"] == "sender@example.com"
