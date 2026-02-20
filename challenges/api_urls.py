"""
API URLs for challenges (REST framework API endpoints only)
"""
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet,
    ChallengeViewSet,
    ChallengeFileViewSet,
    HintViewSet
)
from .instance_views import ChallengeInstanceViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'challenges', ChallengeViewSet, basename='challenge')
router.register(r'files', ChallengeFileViewSet, basename='challengefile')
router.register(r'hints', HintViewSet, basename='hint')
router.register(r'instances', ChallengeInstanceViewSet, basename='instance')

urlpatterns = router.urls
