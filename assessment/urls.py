from django.urls import path
from assessment.views import *

urlpatterns = [
    path("", assessment_list, name="assessment_list"),
    path('signup/',user_signup,name='signup'),
    path('signin/',user_login,name='signin'),
    path('signout/',user_logout,name='signout'),
    path("add-content/", process_question_form, name="add_content"),
    path("edit_content/<int:id>/",process_question_form,name="edit_content"),
    path("generate-assessment/", generate_assessment, name="generate_assessment"),
    path("assessment/<int:id>/<str:slug>/", take_assessment, name="take_assessment"),
    path("submit-assessment/<int:id>/<str:slug>/", submit_assessment, name="submit_assessment"),
    path("activate-deactivate-assessment/<int:id>/", activate_deactivate_assessment, name="activate_deactivate_assessment"),
    path("result-page/<int:result_id>/", result_page, name="result_page"),
    path("correct_answer/<int:id>/",get_correct_answer,name="ishow_correct_answer"),
    path("assessment-results/<int:id>/", assessment_results, name="assessment_results"),
    path("organization-report/", organization_report, name="organization_report"),
    path('download-results/', download_results_csv, name='download_results_csv'),
    path("display-all-questions/", display_all_questions, name="display_all_questions"),
    path("download_pdf/", download_pdf, name="download_pdf"),
    path("assessment-job/<str:job_id>/", assessment_job_status, name="assessment_job_status"),
    # API
    path("api/assessment-list/<int:id>", get_assessment_results, name="assessment_list_api"),
    path("api/import-questions/", import_questions_preview_api, name="import_questions_preview_api"),
    path("api/import-questions/sample-template/", import_questions_sample_template_api, name="import_questions_sample_template_api"),
    path("api/organization-report/", get_organization_report_data, name="organization_report_api"),
    path("api/run-summary-report/", run_summary_report_command, name="run_summary_report_command"),
    # Tools
    path("tools/m4a-to-mp3/", m4a_to_mp3_tool, name="m4a_to_mp3_tool"),
]

handler404 = "assessment.views.errors.handler404"
handler500 = "assessment.views.errors.handler500"
