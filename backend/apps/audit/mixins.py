from .services import record_audit_event


class AuditMutationMixin:
    audit_object_type = None

    def _audit_object_type(self, instance) -> str:
        return self.audit_object_type or instance._meta.model_name

    def perform_create(self, serializer):
        instance = serializer.save()
        record_audit_event(
            actor=self.request.user,
            organization=getattr(instance, "organization", None),
            action=f"{self._audit_object_type(instance)}.create",
            object_type=self._audit_object_type(instance),
            object_id=str(instance.pk),
            object_repr=str(instance),
            metadata={"changes": serializer.validated_data},
            request=self.request,
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        record_audit_event(
            actor=self.request.user,
            organization=getattr(instance, "organization", None),
            action=f"{self._audit_object_type(instance)}.update",
            object_type=self._audit_object_type(instance),
            object_id=str(instance.pk),
            object_repr=str(instance),
            metadata={"changes": serializer.validated_data},
            request=self.request,
        )

    def perform_destroy(self, instance):
        object_type = self._audit_object_type(instance)
        object_id = str(instance.pk)
        object_repr = str(instance)
        organization = getattr(instance, "organization", None)
        instance.delete()
        record_audit_event(
            actor=self.request.user,
            organization=organization,
            action=f"{object_type}.delete",
            object_type=object_type,
            object_id=object_id,
            object_repr=object_repr,
            request=self.request,
        )

