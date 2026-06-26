curl -X POST "https://gyanyatra.prishni.in/api/run-summary-report/" \
  -H "Content-Type: application/json" \
  -H "X-REPORT-TOKEN: B1p8xLguwio=" \
  -d '{
    "user_ids": "2",
    "report_type": "weekly",
    "delivery": "email",
    "exclude_assessment_ids": "56,11,9,21",
    "file_format": "xlsx",
    "output_dir": "reports"
  }'
