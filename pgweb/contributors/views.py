import hashlib

from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseNotModified, Http404

from pgweb.util.contexts import render_pgweb
from pgweb.util.image import get_image_contenttype_from_bytes

from .models import ContributorType, Contributor, Badge, Badgeholder


def completelist(request):
    contributortypes = list(ContributorType.objects.all())
    return render_pgweb(request, 'community', 'contributors/list.html', {
        'contributortypes': contributortypes,
    })


def peoplelist(request):
    people = Contributor.objects.prefetch_related('user')
    badges = Badge.objects.filter(approved=True)
    return render_pgweb(request, 'community', 'contributors/people.html', {
        'people': people,
        'badges': badges,
    })


def badge_view(request, badgeid):
    badge = get_object_or_404(Badge, id=badgeid, approved=True)
    # badge holders are users, but we want to show only users with a contributor object here
    holders = Badgeholder.objects.filter(badge=badge, user__contributor__isnull=False). \
        prefetch_related('user__contributor'). \
        order_by('user__contributor__lastname', 'user__contributor__firstname')
    return render_pgweb(request, 'community', 'contributors/badge.html', {
        'badge': badge,
        'holders': holders,
    })


def profile(request, username):
    contributor = get_object_or_404(Contributor, user__username=username)
    badges = Badgeholder.objects.filter(user=contributor.user, badge__approved=True)
    return render_pgweb(request, 'community', 'contributors/profile.html', {
        'contributor': contributor,
        'badges': badges,
    })


def badge_image(request, badgeid):
    badge = get_object_or_404(Badge.objects.only('id', 'imagedata'), id=badgeid, approved=True)
    if not badge.imagedata:
        raise Http404
    etag = '"' + hashlib.md5(bytes(badge.imagedata)).hexdigest() + '"'
    if request.headers.get('If-None-Match') == etag:
        return HttpResponseNotModified()
    return HttpResponse(
        bytes(badge.imagedata),
        content_type=get_image_contenttype_from_bytes(badge.imagedata[:8]),
    )
