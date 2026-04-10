from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Branch
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db.models import QuerySet


def health(_request):
    return JsonResponse({"module": "branches", "status": "ok"})


@staff_member_required
def list_branches(request):
    qs: 'QuerySet[Branch]' = Branch.objects.filter(is_active=True).order_by('name')
    data = [{"id": b.id, "name": b.name} for b in qs]  # type: ignore[attr-defined]
    return JsonResponse({"results": data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_branch(request):
    user = request.user
    if not hasattr(user, 'role') or user.role not in ['admin', 'owner']:
        return Response({'error': 'Permission denied'}, status=403)
    
    data = request.data
    name = data.get('name')
    slug = data.get('slug')
    
    if not name or not slug:
        return Response({'error': 'name and slug are required'}, status=400)
    
    if Branch.objects.filter(slug=slug).exists():
        return Response({'error': 'Branch with this slug already exists'}, status=400)
    
    branch: Branch = Branch.objects.create(
        name=name,
        slug=slug,
        description=data.get('description', ''),
        is_active=data.get('is_active', True),
        created_by=user,
        owner=user if user.role == 'owner' else None
    )
    
    return Response({
        'id': branch.id,  # type: ignore[attr-defined]
        'name': branch.name,
        'slug': branch.slug,
        'description': branch.description,
        'is_active': branch.is_active,
        'created_at': branch.created_at.isoformat()
    }, status=201)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_branch(request, branch_id):
    user = request.user
    if not hasattr(user, 'role') or user.role not in ['admin', 'owner']:
        return Response({'error': 'Permission denied'}, status=403)
    
    branch: Branch = get_object_or_404(Branch, id=branch_id)
    data = request.data
    
    if 'name' in data:
        branch.name = data['name']
    if 'slug' in data and data['slug'] != branch.slug:
        if Branch.objects.filter(slug=data['slug']).exists():
            return Response({'error': 'Branch with this slug already exists'}, status=400)
        branch.slug = data['slug']
    if 'description' in data:
        branch.description = data['description']
    if 'is_active' in data:
        branch.is_active = data['is_active']
    
    branch.save()
    
    return Response({
        'id': branch.id,  # type: ignore[attr-defined]
        'name': branch.name,
        'slug': branch.slug,
        'description': branch.description,
        'is_active': branch.is_active,
        'updated_at': branch.updated_at.isoformat()
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_branch(request, branch_id):
    user = request.user
    if not hasattr(user, 'role') or user.role != 'owner':
        return Response({'error': 'Only owner can delete branches'}, status=403)
    
    branch: Branch = get_object_or_404(Branch, id=branch_id)
    branch_name = branch.name
    branch.delete()
    
    return Response({
        'message': f'Branch "{branch_name}" deleted successfully'
    }, status=200)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_branch(request, branch_id):
    user = request.user
    if not hasattr(user, 'role') or user.role not in ['admin', 'owner', 'manager']:
        return Response({'error': 'Permission denied'}, status=403)
    
    branch: Branch = get_object_or_404(Branch, id=branch_id)
    
    return Response({
        'id': branch.id,  # type: ignore[attr-defined]
        'name': branch.name,
        'slug': branch.slug,
        'description': branch.description,
        'is_active': branch.is_active,
        'created_at': branch.created_at.isoformat(),
        'updated_at': branch.updated_at.isoformat()
    })

