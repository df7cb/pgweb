# APT repository interface for the PostgreSQL website
# Authors: Adrian Vondendriesch <adrian.vondendriesch@credativ.de>
#          Christoph Berg <christoph.berg@credativ.de>

from pgweb.util.contexts import render_pgweb
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.db import connection
from models import *
from utils import *

def apt(request):
    return render_pgweb(request, 'apt', 'apt/apt.html', {})

def sources(request, release):
    source_list_entries = SourceList.objects.filter(suite__release_id=release).order_by('source__source')
    if not len(source_list_entries):
        raise Http404

    sources = [entry.source for entry in source_list_entries]

    return render_pgweb(request, 'apt', 'apt/sources.html', {
        'release': release,
        'sources': sources,
        })

def source(request, package_name, release='sid-pgdg', component=None, filename=None):

    source_list_entries = SourceList.objects.filter(source__source__exact=package_name)
    suites = [e.suite for e in source_list_entries]

    if release:
        source_list_entries = source_list_entries.filter(suite__release_id__exact=release)
    if component:
        source_list_entries = source_list_entries.filter(suite__component_id__exact=component)

    sources = [s.source for s in source_list_entries]

    # check if at least one source package was found
    if not len(sources):
        raise Http404

    source = sources[0]
    current_component = source_list_entries[0].suite.component_id
    current_release = source_list_entries[0].suite.release_id

    binaries           = [binary.strip() for binary in source.binary.split(',')]

    if filename:
        if filename == 'copyright':
            title = 'Copyright file'
            content = source.copyright
        elif filename == 'debchangelog':
            title = 'Debian changelog'
            content = source.debchangelog
        else:
            title = 'Upstream changelog'
            content = source.changelog
        return render_pgweb(request, 'apt', 'apt/source_file.html', {
                'package': source,
                'filename': filename,
                'title': title,
                'content': content,
                'current_release': current_release,
                'current_component': current_component,
                'binaries': binaries,
            })

    source_list_entries = source_list_entries.filter(suite__release_id__exact=current_release)
    components = [e.suite.component_id for e in source_list_entries]

    # create dependency list
    build_dependencies = build_related_list(source.build_depends, current_release)

    return render_pgweb(request, 'apt', 'apt/source.html', {
            'package': source,
            'build_dependencies': build_dependencies,
            'distributions': suites,
            'current_release': current_release,
            'components': components,
            'current_component': current_component,
            'files': source.files_set.all(),
            'binaries': binaries
        })

def binary_contents(request, package_name, release, component, arch):

    # fix contents for all packages
    if arch == 'all':
        arch = 'amd64'

    binary_list_entries = PackageList.objects.filter(package__package__exact=package_name, suite__release_id__exact=release, suite__component_id__exact=component, suite__architecture_id__exact=arch)

    if not len(binary_list_entries):
        raise Http404

    binary_list = binary_list_entries[0]
    binary = binary_list.package
    contents = binary.packagecontents_set.all().order_by("filename")

    return render_pgweb(request, 'apt', 'apt/binary_contents.html', {
        'package': binary,
        'current_release': release,
        'current_component': component,
        'contents': contents,
      })

def binary(request, package_name, release='sid-pgdg', component='main'):

    binary_list_entries = PackageList.objects.filter(package__package__exact=package_name)
    suites = [e.suite for e in binary_list_entries.distinct('suite__release')]

    if release:
        binary_list_entries = binary_list_entries.filter(suite__release__exact=release)
    components = [c.suite.component for c in binary_list_entries.distinct('suite__component')]
    if component:
        binary_list_entries = binary_list_entries.filter(suite__component_id__exact=component)

    # check if at least on source package was found
    if not len(binary_list_entries):
        raise Http404

    binary = binary_list_entries[0].package
    current_component = binary_list_entries[0].suite.component_id
    current_release = binary_list_entries[0].suite.release_id

    dependencies = build_related_list(binary.depends, current_release)
    recommendations = build_related_list(binary.recommends, current_release)
    suggestions = build_related_list(binary.suggests, current_release)

    return render_pgweb(request, 'apt', 'apt/binary.html', {
        'package': binary,
        'dependencies': dependencies,
        'recommendations': recommendations,
        'distributions': suites,
        'current_release': current_release,
        'suggestions': suggestions,
        'components': components,
        'current_component': current_component,
        'files': None,
        'downloads': Package.objects.filter(package=package_name, version=binary.version)
      })

def distributions(request):
    releases = Release.objects.order_by("vendor", "relversion", "release")

    return render_pgweb(request, 'apt', 'apt/distributions.html', {
        'releases': releases,
      })

def binaries(request, release, component_name=None, architecture_name=None):

    if not architecture_name:
        architecture_name = 'amd64'

    suites = Suite.objects.filter(release=release, architecture=architecture_name)
    components = [d.component for d in suites.distinct('component')]

    if not component_name:
        component_name = 'main'

    suites = suites.filter(component_id=component_name)

    if not len(suites):
        raise Http404

    suite = suites[0]

    binary_lists = suite.packagelist_set.all().order_by('package__package')
    binaries = [binary_list.package for binary_list in binary_lists]

    return render_pgweb(request, 'apt', 'apt/binaries.html', {
        'suite': suite,
        'components': components,
        'binaries': binaries
      })

def search(request):
    if 'package' in request.GET and request.GET['package']:
        package = request.GET['package']

        result_binaries = Package.objects.distinct('package').filter(package__icontains=package)
        result_sources = Source.objects.distinct('source').filter(source__icontains=package)

        return render_pgweb(request, 'apt', 'apt/search.html', {
            'result': True,
            'package': package,
            'result_binaries': result_binaries,
            'result_sources': result_sources,
        })

    elif 'file' in request.GET and request.GET['file']:
        filename = request.GET['file']

        maxresults = 100
        result_filenames = PackageContents.objects.distinct('filename', 'package__package').filter(filename__contains=filename).order_by("filename")[:maxresults]

        return render_pgweb(request, 'apt', 'apt/search.html', {
            'filename': filename,
            'maxresults': maxresults,
            'result_filenames': result_filenames,
        })

    else:
        return render_pgweb(request, 'apt', 'apt/search.html', {
        })

def madison(request):
    """Query interface compatible with rmadison(1)"""

    if 'package' in request.GET and request.GET['package']:
        package = request.GET['package']

        sql1 = """SELECT package, version, release_id, component_id, array_agg(architecture_id) AS architecture FROM (
            SELECT package, version, release_id, component_id, architecture_id
                FROM apt_packagelist pl
                JOIN apt_suite s ON (suite_id = s.id)
                JOIN apt_package p ON (package_id = p.id)
            UNION ALL SELECT source, srcversion, release_id, component_id, 'source'
                FROM apt_sourcelist sl
                JOIN apt_srcsuite ss ON (suite_id = ss.id)
                JOIN apt_source s ON (source_id = s.id)
            ORDER BY package, version, release_id, component_id, architecture_id
            ) AS r WHERE """
        sql2 = "GROUP BY package, version, release_id, component_id"

        qual = []
        args = [package]
        configdisplay = 'none'

        r = ''
        if 'r' in request.GET:
            r = 'checked'
            qual.append('package ~ %s')
            configdisplay = 'block'
        else:
            qual.append('package = %s')

        a = ''
        if 'a' in request.GET and request.GET['a']:
            a = request.GET['a']
            qual.append('architecture_id = %s')
            args.append(a)
            configdisplay = 'block'

        c = ''
        if 'c' in request.GET and request.GET['c']:
            c = request.GET['c']
            qual.append('component_id = %s')
            args.append(c)
            configdisplay = 'block'

        s = '' # distributions are called suites in dak
        if 's' in request.GET and request.GET['s']:
            s = request.GET['s']
            qual.append('release_id = %s')
            args.append(s)
            configdisplay = 'block'

        cursor = connection.cursor()
        cursor.execute(sql1 + " AND ".join(qual) + sql2, args)
        return_set = cursor.fetchall()

        plen = 1
        vlen = 1
        rlen = 1
        for (pkg, version, release, component, architecture) in return_set:
            if component != 'main':
                release += '/' + component
            if len(pkg) > plen:
                plen = len(pkg)
            if len(version) > vlen:
                vlen = len(version)
            if len(release) > rlen:
                rlen = len(release)
        fstr = " %%-%ds | %%-%ds | %%-%ds | %%s\n" % (plen, vlen, rlen)

        content = ''
        for (pkg, version, release, component, architecture) in return_set:
            if component != 'main':
                release += '/' + component
            content += fstr % (pkg, version, release, ", ".join(architecture))

        if 'text' in request.GET:
            return HttpResponse(content, content_type='text/plain')

        return render_pgweb(request, 'apt', 'apt/madison.html', {
            'result': True,
            'package': package,
            'r': r,
            # no need to pass checkbox 'text' value here
            'a': a,
            'c': c,
            's': s,
            'configdisplay': configdisplay,
            'content': content,
        })

    else:
        return render_pgweb(request, 'apt', 'apt/madison.html', {
            'configdisplay': 'none',
        })

def qa(request, query=None):
    result = None

    if True or query == None: # TODO: fix the SQL queries
        description = "APT Repository Quality Assurance"
        sql = None

    elif query == "binary_missing_on_architecture":
        description = "Binary package versions that exist only on one architecture"
        sql = """select * from apt_pkg a where not exists
            (select * from apt_pkg b where a.package = b.package and a.version = b.version and a.architecture_id <> b.architecture_id)
            order by release_id, package, version"""

    elif query == "wrong_tag_in_version":
        description = "Package versions with wrong pgdg tag"
        sql = """select p.* from apt_pkg p join apt_release r on (p.release_id = r.release)
            where version !~ case
                when release = 'sid-pgdg' then 'pgdg'
                when release = 'lenny-pgdg' then 'pg(dg|apt)50'
                when release = 'etch-pgdg' then 'pg(dg|apt)40'
                when vendor_id = 'Debian' then 'pgdg'||relversion||0
                when release = 'precise-pgdg' then 'pgdg12.4'
                when release = 'lucid-pgdg' then 'pgdg10.4'
                when vendor_id = 'Ubuntu' then 'pgdg'||relversion
            end
            and r.active
            order by release_id, package, version, architecture_id"""

    elif query == "binary_without_source":
        description = "Binary packages without source"
        sql = """select * from apt_pkg p where not exists
            (select * from apt_source s where (p.source, p.srcversion) = (s.source, s.srcversion))
            order by release_id, package, version, architecture_id"""

    elif query == "binary_in_sid_only":
        description = "Binary packages in sid-pgdg missing in other suites"
        sql = """SELECT DISTINCT sidpkg.package, sidpkg.version, sidpkg.source, sidpkg.srcversion,
            rel.release AS missing_release FROM apt_pkg sidpkg
            JOIN apt_release rel ON (true)
            LEFT JOIN apt_pkg p ON (rel.release = p.release_id and sidpkg.package = p.package)
            WHERE sidpkg.release_id = 'sid-pgdg' AND rel.release <> 'sid-pgdg' AND rel.active
                AND p.package IS NULL
            ORDER BY sidpkg.package, missing_release"""

    elif query == "binary_with_old_version":
        description = "Binary packages with versions different from sid-pgdg"
        sql = """SELECT sidpkg.release_id, sidpkg.component_id, sidpkg.package, sidpkg.version,
                sidpkg.architecture_id, p.release_id, p.version FROM apt_pkg sidpkg
            JOIN apt_pkg p ON (sidpkg.package = p.package AND sidpkg.component_id = p.component_id AND sidpkg.architecture_id = p.architecture_id)
            WHERE sidpkg.release_id = 'sid-pgdg'
                AND regexp_replace(sidpkg.version, '.pgdg.*', '') <> regexp_replace(p.version, '.pgdg.*', '')
            ORDER BY sidpkg.component_id, sidpkg.package, sidpkg.architecture_id, p.release_id"""

    elif query == "source_without_binary":
        description = "Source packages without binaries"
        sql = """SELECT source, srcversion FROM apt_source s WHERE NOT EXISTS
            (SELECT * FROM apt_pkg p WHERE (s.source, s.srcversion) = (p.source, p.srcversion))"""

    else:
        raise Http404

    if sql:
        cursor = connection.cursor()
        cursor.execute(sql)
        result = cursor.fetchall()

    return render_pgweb(request, 'apt', 'apt/qa.html', {
        'query': query,
        'description': description,
        'result': result,
    })
