from jobharbor.connectors.ycombinator import YCombinatorConnector


def test_ycombinator_fetch_jobs_extracts_embedded_job_postings() -> None:
    html = """
    <html>
      <script>
        var payload = {
          &quot;jobPostings&quot;:[
            {
              &quot;id&quot;:89594,
              &quot;title&quot;:&quot;Senior Android Engineer&quot;,
              &quot;url&quot;:&quot;/companies/varos/jobs/FILSDCi-senior-android-engineer&quot;,
              &quot;location&quot;:&quot;Remote (US)&quot;,
              &quot;companyName&quot;:&quot;Varos&quot;,
              &quot;createdAt&quot;:&quot;about 1 month&quot;,
              &quot;prettyRole&quot;:&quot;Engineering&quot;
            }
          ]
        };
      </script>
    </html>
    """

    connector = YCombinatorConnector(fetch_text=lambda _: html)
    jobs = connector.fetch_jobs()

    assert len(jobs) == 1
    assert jobs[0]["external_id"] == "89594"
    assert jobs[0]["title"] == "Senior Android Engineer"
    assert jobs[0]["company"] == "Varos"
    assert jobs[0]["location"] == "Remote (US)"
    assert jobs[0]["url"] == "https://www.workatastartup.com/companies/varos/jobs/FILSDCi-senior-android-engineer"
    assert jobs[0]["description"] == "Engineering"


def test_ycombinator_fetch_jobs_handles_missing_payload() -> None:
    connector = YCombinatorConnector(fetch_text=lambda _: "<html><body>no jobs payload</body></html>")
    assert connector.fetch_jobs() == []

