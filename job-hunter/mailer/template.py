from datetime import date

from models import Job


def render_email(
    scored_jobs: list[tuple[Job, int]],
    stats: dict,
    source_status: dict[str, bool],
) -> tuple[str, str]:
    today = date.today().strftime("%B %d, %Y")
    count = len(scored_jobs)
    subject = f"Job Hunter Daily \u2014 {today} ({count} new listings)"

    if not scored_jobs:
        body = _render_empty(stats, source_status, today)
    else:
        body = _render_full(scored_jobs, stats, source_status, today)

    return subject, body


def _render_full(scored_jobs, stats, source_status, today):
    rows = ""
    for i, (job, score) in enumerate(scored_jobs, 1):
        salary_cell = job.salary if job.salary else "\u2014"
        rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee;">{i}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;"><strong>{score}</strong></td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{job.title}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{job.company}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{job.location}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{salary_cell}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">
                <a href="{job.url}" style="color:#2563eb;">Apply &rarr;</a>
            </td>
        </tr>"""

    sources = " | ".join(
        f"{name} {'&#10003;' if ok else '&#10007;'}"
        for name, ok in source_status.items()
    )

    return f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;">
        <h2>Job Hunter Daily &mdash; {today}</h2>
        <p>Hey Alvin,</p>
        <p>Here are today's top matches, ranked by fit:</p>
        <table style="border-collapse:collapse;width:100%;font-size:14px;">
            <thead>
                <tr style="background:#f8f9fa;">
                    <th style="padding:8px;text-align:left;">#</th>
                    <th style="padding:8px;text-align:left;">Score</th>
                    <th style="padding:8px;text-align:left;">Title</th>
                    <th style="padding:8px;text-align:left;">Company</th>
                    <th style="padding:8px;text-align:left;">Location</th>
                    <th style="padding:8px;text-align:left;">Salary</th>
                    <th style="padding:8px;text-align:left;">Link</th>
                </tr>
            </thead>
            <tbody>{rows}
            </tbody>
        </table>
        <hr style="margin:20px 0;border:none;border-top:1px solid #ddd;">
        <p style="font-size:12px;color:#666;">
            Sources checked: {sources}<br>
            Total scraped: {stats['total_scraped']} | New today: {stats['new_today']} | Passed filters: {stats['passed_filters']}
        </p>
    </body>
    </html>
    """


def _render_empty(stats, source_status, today):
    sources = " | ".join(
        f"{name} {'&#10003;' if ok else '&#10007;'}"
        for name, ok in source_status.items()
    )
    return f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;">
        <h2>Job Hunter Daily &mdash; {today}</h2>
        <p>Hey Alvin,</p>
        <p>No matching jobs found today. This could mean all today's listings were already seen, or scrapers hit rate limits.</p>
        <hr style="margin:20px 0;border:none;border-top:1px solid #ddd;">
        <p style="font-size:12px;color:#666;">
            Sources checked: {sources}<br>
            Total scraped: {stats['total_scraped']} | New today: {stats['new_today']} | Passed filters: {stats['passed_filters']}
        </p>
    </body>
    </html>
    """
