from rest_framework import serializers
from .models import AssessmentResult,Subject

class AssessmentResultSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()
    assessment = serializers.SerializerMethodField()
    start_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    end_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = AssessmentResult
        exclude = ['answers']

    def get_organization(self, obj):
        return {
            "name": obj.organization.name if obj.organization else None,
        }

    def get_assessment(self, obj):
        return {
            "name": obj.assessment.name if obj.assessment else None,
            "level": obj.assessment.level if obj.assessment else None,
            "subject": Subject.getlabel(obj.assessment.subject) if obj.assessment and obj.assessment.subject else None,
            "sub_level": obj.assessment.sub_level if obj.assessment and obj.assessment.sub_level else None
        }

