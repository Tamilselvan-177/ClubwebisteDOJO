from django.urls import path
from .views import blogsView, blogView

app_name="Blogs"

urlpatterns = [
    path("", blogsView.as_view(), name="blogs"),
    path("<slug:slug>/", blogView.as_view(), name="blog"),
]