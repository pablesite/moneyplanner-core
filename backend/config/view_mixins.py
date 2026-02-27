class UserScopedQuerySetMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(user=self.request.user)
