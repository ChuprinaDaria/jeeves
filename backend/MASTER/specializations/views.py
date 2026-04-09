from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from .models import Specialization


def health(_request):
    return JsonResponse({"module": "specializations", "status": "ok"})


@staff_member_required
def list_specializations(request):
    qs = Specialization.objects.filter(is_active=True)
    branch_id = request.GET.get('branch_id')
    if branch_id:
        qs = qs.filter(branch_id=branch_id)
    qs = qs.order_by('name')
    data = [{"id": s.id, "name": s.name, "branch_id": s.branch_id} for s in qs]
    return JsonResponse({"results": data})


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Specialization
from MASTER.branches.models import Branch


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_specialization(request):
    user = request.user
    if not hasattr(user, 'role') or user.role not in ['admin', 'owner', 'manager']:
        return Response({'error': 'Permission denied'}, status=403)
    
    data = request.data
    name = data.get('name')
    slug = data.get('slug')
    branch_id = data.get('branch_id')
    
    if not name or not slug or not branch_id:
        return Response({'error': 'name, slug and branch_id are required'}, status=400)
    
    branch = get_object_or_404(Branch, id=branch_id)
    
    if Specialization.objects.filter(slug=slug).exists():
        return Response({'error': 'Specialization with this slug already exists'}, status=400)
    
    specialization = Specialization.objects.create(
        branch=branch,
        name=name,
        slug=slug,
        description=data.get('description', ''),
        is_active=data.get('is_active', True),
        created_by=user
    )
    
    return Response({
        'id': specialization.id,
        'name': specialization.name,
        'slug': specialization.slug,
        'description': specialization.description,
        'branch_id': specialization.branch_id,
        'branch_name': branch.name,
        'is_active': specialization.is_active,
        'created_at': specialization.created_at.isoformat()
    }, status=201)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_specialization(request, spec_id):
    user = request.user
    if not hasattr(user, 'role') or user.role not in ['admin', 'owner', 'manager']:
        return Response({'error': 'Permission denied'}, status=403)
    
    specialization = get_object_or_404(Specialization, id=spec_id)
    data = request.data
    
    if 'name' in data:
        specialization.name = data['name']
    if 'slug' in data and data['slug'] != specialization.slug:
        if Specialization.objects.filter(slug=data['slug']).exists():
            return Response({'error': 'Specialization with this slug already exists'}, status=400)
        specialization.slug = data['slug']
    if 'description' in data:
        specialization.description = data['description']
    if 'is_active' in data:
        specialization.is_active = data['is_active']
    if 'branch_id' in data:
        branch = get_object_or_404(Branch, id=data['branch_id'])
        specialization.branch = branch
    
    specialization.save()
    
    return Response({
        'id': specialization.id,
        'name': specialization.name,
        'slug': specialization.slug,
        'description': specialization.description,
        'branch_id': specialization.branch_id,
        'is_active': specialization.is_active,
        'updated_at': specialization.updated_at.isoformat()
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_specialization(request, spec_id):
    user = request.user
    if not hasattr(user, 'role') or user.role not in ['admin', 'owner']:
        return Response({'error': 'Only admin and owner can delete specializations'}, status=403)
    
    specialization = get_object_or_404(Specialization, id=spec_id)
    spec_name = specialization.name
    specialization.delete()
    
    return Response({
        'message': f'Specialization "{spec_name}" deleted successfully'
    }, status=200)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_specialization(request, spec_id):
    user = request.user
    if not hasattr(user, 'role') or user.role not in ['admin', 'owner', 'manager']:
        return Response({'error': 'Permission denied'}, status=403)
    
    specialization = get_object_or_404(Specialization, id=spec_id)
    
    return Response({
        'id': specialization.id,
        'name': specialization.name,
        'slug': specialization.slug,
        'description': specialization.description,
        'branch_id': specialization.branch_id,
        'branch_name': specialization.branch.name,
        'is_active': specialization.is_active,
        'created_at': specialization.created_at.isoformat(),
        'updated_at': specialization.updated_at.isoformat()
    })

