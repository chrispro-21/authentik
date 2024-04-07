"""SCIM Group Views"""

from django.conf import settings
from django.core.paginator import Paginator
from django.db.transaction import atomic
from django.http import Http404, QueryDict
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from authentik.core.models import Group
from authentik.providers.scim.clients.schema import Group as SCIMGroupModel
from authentik.sources.scim.models import SCIMSourceGroup
from authentik.sources.scim.views.v2.base import SCIMView


class GroupsView(SCIMView):
    """SCIM Group view"""

    def group_to_scim(self, scim_group: SCIMSourceGroup) -> dict:
        """Convert Group to SCIM data"""
        payload = SCIMGroupModel(
            id=str(scim_group.group.pk),
            externalId=scim_group.id,
            displayName=scim_group.group.name,
        )
        # payload = {
        #     "meta": {
        #         "resourceType": "User",
        #         "created": scim_user.user.date_joined,
        #         # TODO: use events to find last edit?
        #         "lastModified": scim_user.user.date_joined,
        #         "location": self.request.build_absolute_uri(
        #             reverse(
        #                 "authentik_sources_scim:v2-users",
        #                 kwargs={
        #                     "source_slug": self.kwargs["source_slug"],
        #                     "user_id": str(scim_user.user.pk),
        #                 },
        #             )
        #         ),
        #     },
        # }
        return payload.model_dump(
            mode="json",
            exclude_unset=True,
        )

    def get(self, request: Request, group_id: str | None = None, **kwargs) -> Response:
        """List Group handler"""
        if group_id:
            connection = (
                SCIMSourceGroup.objects.filter(source=self.source, id=group_id)
                .select_related("group")
                .first()
            )
            if not connection:
                raise Http404
            return Response(self.group_to_scim(connection))
        connections = (
            SCIMSourceGroup.objects.filter(source=self.source)
            .select_related("group")
            .order_by("pk")
        )
        per_page = settings.REST_FRAMEWORK["PAGE_SIZE"]
        paginator = Paginator(connections, per_page=per_page)
        start_index = int(request.query_params.get("startIndex", 1))
        page = paginator.page(int(max(start_index / per_page, 1)))
        return Response(
            {
                "totalResults": paginator.count,
                "itemsPerPage": per_page,
                "startIndex": page.start_index(),
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
                "Resources": [self.group_to_scim(connection) for connection in page],
            }
        )

    @atomic
    def update_group(self, connection: SCIMSourceGroup | None, data: QueryDict):
        """Partial update a group"""
        group = connection.group if connection else Group()
        if "name" in data:
            group.name = data.get("displayName")
        if group.name == "":
            raise ValidationError("Invalid group")
        group.save()
        if not connection:
            connection, _ = SCIMSourceGroup.objects.get_or_create(
                source=self.source,
                group=group,
                attributes=data,
                id=data.get("externalId"),
            )
        else:
            connection.attributes = data
            connection.save()
        return connection

    def post(self, request: Request, **kwargs) -> Response:
        """Create group handler"""
        connection = SCIMSourceGroup.objects.filter(
            source=self.source,
            id=request.data.get("externalId"),
        ).first()
        if connection:
            self.logger.debug("Found existing group")
            return Response(status=409)
        connection = self.update_group(None, request.data)
        return Response(self.group_to_scim(connection), status=201)

    def put(self, request: Request, group_id: str, **kwargs) -> Response:
        """Update group handler"""
        connection = SCIMSourceGroup.objects.filter(source=self.source, id=group_id).first()
        if not connection:
            raise Http404
        connection = self.update_group(connection, request.data)
        return Response(self.group_to_scim(connection), status=200)

    @atomic
    def delete(self, request: Request, group_id: str, **kwargs) -> Response:
        """Delete group handler"""
        connection = SCIMSourceGroup.objects.filter(source=self.source, id=group_id).first()
        if not connection:
            raise Http404
        connection.group.delete()
        connection.delete()
        return Response({}, status=204)