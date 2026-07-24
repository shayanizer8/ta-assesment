import logging

logger = logging.getLogger("ta_assessment.tasks")


def send_submission_confirmation_email(candidate_email: str, submission_id: str):
    """
    Background task stub simulating sending a confirmation email to the candidate.
    In production, this would dispatch a task to a background worker queue (e.g. Celery / SQS / Redis).
    """
    logger.info(f"[STUB] Confirmation email dispatched to candidate {candidate_email} for submission {submission_id}")


def queue_file_antivirus_scan(submission_id: str, file_reference: str):
    """
    Background task stub simulating queuing a file for anti-virus and malware scanning.
    In production, this would trigger an async security pipeline and update submission scan_status.
    """
    logger.info(f"[STUB] File reference '{file_reference}' for submission {submission_id} queued for security scan")
