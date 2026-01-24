# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .models import UserSettings
from .serializers import UserSettingsSerializer


class UserSettingsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
        data = UserSettingsSerializer(settings_obj).data
        return Response(data)

    def put(self, request):
        settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
        serializer = UserSettingsSerializer(settings_obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
