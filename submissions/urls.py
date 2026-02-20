from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SubmissionViewSet, ScoreViewSet, ViolationViewSet
from .monitoring_views import MonitoringViewSet, ViolationManagementViewSet

router = DefaultRouter()
router.register(r'submissions', SubmissionViewSet, basename='submission')
router.register(r'scores', ScoreViewSet, basename='score')
router.register(r'violations', ViolationViewSet, basename='violation')
router.register(r'violations-management', ViolationManagementViewSet, basename='violation-management')
router.register(r'monitoring', MonitoringViewSet, basename='monitoring')

urlpatterns = [
    path('', include(router.urls)),
]

