#!/usr/bin/env python

# debmirror -v -h apt.postgresql.org -r pub/repos/apt --method=http -d sid-pgdg,buster-pgdg --omit-suite-symlinks -s main,9.3,9.4,9.5,9.6,10,11,12 -a source,amd64,i386,ppc64el --exclude='\.deb$' --getcontents --no-check-gpg /srv/repo

import apt_pkg, markdown, os, re, sys, time, gzip, subprocess

# Set up for accessing django
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings_local")
import sys
sys.path.append('../../pgweb')
from django.conf import settings
#from apt import models as c

#from core.models import ImportedRSSFeed, ImportedRSSItem
from django.db import transaction, connection

#transaction.enter_transaction_management()
#transaction.managed()

config = {
        'FILTER': [
            'testing',
            'deprecated'
            ]
        }

running_config = {
        'VERBOSE': 0,
        'FORCE':   False,
        'DISTONLY': False,
        }

usage = """
%s [options]
    -h  show this help
    -v  verbose
    -f  force (deletes every package before insert)
    -d  ignore errors from dscextract (useful for running on dists/ only)
""" % sys.argv[0]

def dir_filter(string):
    for f in config['FILTER']:
        if f in string:
            return 0
    return 1

def getArchitectureNames(directories):
    binary_pattern = 'binary-'
    binaries = []
    for directory in directories:
        if re.match(binary_pattern, directory):
            binaries.append(directory.split('-')[1])

    return binaries

def buildFileDict(flist):
    fdict = {}
    for line in flist:
        columns = line.split('\t')
        if len(columns) > 1 and columns[0] != 'FILE':
            filename = '/' + columns[0]
            packagename = columns[1].split('/')[-1].strip()
            try:
                fdict[packagename]
            except:
                fdict[packagename] = []
            fdict[packagename].append(filename)
            #print "P-Name:", packagename
    return fdict

def main(*args, **kwargs):
    running_config['VERBOSE'] = 0

    # args
    if len(args) > 0:
        for arg in args[0]:
            if arg == '-v':
                running_config['VERBOSE'] += 1
            if arg == '-f':
                running_config['FORCE'] = True
            if arg == '-d':
                running_config['DISTONLY'] = True
            if arg == '-h':
                print usage
                exit(0)

    cursor = connection.cursor()

    # releases
    base_dir = getattr(settings, 'APT_DIR') + "/dists/"
    releases = [directory for directory in os.listdir(base_dir) \
            if os.path.isdir(os.path.join(base_dir, directory))]
    releases = filter(dir_filter, releases)
    if running_config['VERBOSE'] > 0:
        print "Releases to scan (%s): %s" % \
                (len(releases), ', '.join(releases))

    for release in releases:
        print "%s:" % (release)
        cur_dir = base_dir + release
        components = [component for component in os.listdir(cur_dir) \
                if os.path.isdir(os.path.join(cur_dir, component))]
        components = filter(dir_filter, components)
        if running_config['VERBOSE'] > 0:
            print "\tComponents in %s to scan (%s): %s" % \
                        (release, len(components), ', '.join(components))

        for component in components:
            if running_config['VERBOSE'] > 0:
                print "\t%s:" % (component)

            # insert components, that aren't not yet registered
            sql = """
                    INSERT INTO apt_component
                        SELECT * FROM (VALUES (%s)) comp(component)
                        WHERE NOT EXISTS (
                            SELECT * FROM apt_component
                                WHERE component = comp.component
                        )
                """
            cursor.execute(sql, (component,))

            srcsuite_id, last_update = insertSuite(release, component)
            parseFile(last_update, srcsuite_id, release, component)

            # read binary architectures
            architectures = getArchitectureNames(os.listdir(os.path.join(cur_dir, component)))

            for architecture in architectures:
                # insert architectures, that aren't not yet registered
                sql = """
                        INSERT INTO apt_architecture
                            SELECT * FROM (VALUES (%s)) arch(architecture)
                            WHERE NOT EXISTS (
                                SELECT * FROM apt_architecture
                                    WHERE architecture = arch.architecture
                            )
                    """
                cursor.execute(sql, (architecture,))

                suite_id, last_update = insertSuite(release, component, architecture)
                parseFile(last_update, suite_id, release, component, architecture)

    # update source package descriptions
    sql = """UPDATE apt_source s SET
        short_description = (SELECT short_description FROM apt_package p WHERE (p.source, p.srcversion) = (s.source, s.srcversion) ORDER BY source = p.package DESC, p.package LIMIT 1),
        description = (SELECT description FROM apt_package p WHERE (p.source, p.srcversion) = (s.source, s.srcversion) ORDER BY source = p.package DESC, p.package LIMIT 1)
        WHERE s.short_description IS NULL"""
    cursor.execute(sql)
    transaction.commit()

    connection.close()
    return


def insertSuite(release, component, architecture=None):
    cursor = connection.cursor()

    sql = "SELECT release FROM apt_release WHERE release = %s"
    cursor.execute(sql, (release,))
    if not cursor.fetchone():
        sql = "INSERT INTO apt_release (vendor_id, release, relversion, active) VALUES ('Debian', %s, '', true)"
        cursor.execute(sql, (release,))

    if architecture is None:
        tbl = "srcsuite"
        src = True
    else:
        tbl = "suite"
        src = False

    # check if srcsuite is already in db
    sql = "SELECT id, extract('epoch' from last_update) FROM apt_%s WHERE " % (tbl)
    if src:
        sql = sql + "(release_id, component_id) = (%s, %s) "
        args_tpl = (release, component)
    else:
        sql = sql + "(release_id, component_id, architecture_id) = (%s, %s, %s)"
        args_tpl = (release, component, architecture)
    cursor.execute(sql, args_tpl)

    return_set = cursor.fetchone()

    if return_set:
        suite_id = return_set[0]
        last_update = return_set[1]

    else:
        last_update = None
        sql = "INSERT INTO apt_%s " % (tbl)
        if src:
            sql = sql + "(release_id, component_id) "
            sql = sql + "VALUES (%s, %s) "
            args_tpl = (release, component)
        else:
            sql = sql + "(release_id, component_id, architecture_id) "
            sql = sql + "VALUES (%s, %s, %s) "
            args_tpl = (release, component, architecture)
        sql = sql + "RETURNING id"
        cursor.execute(sql, args_tpl)

        suite_id = cursor.fetchone()

    if running_config['VERBOSE'] and not last_update:
        if src:
            print "\tinserted new source suite (%s, %s)" % (release, component)
        else:
            print "\tinserted new suite (%s, %s, %s)" % (release, component, architecture)

    return suite_id, last_update;

def parseFile(last_update, suite_id, release, component, architecture=None):
    verbose = running_config['VERBOSE']
    cursor = connection.cursor()
    packagesfile = ""
    source_re = re.compile('(.*) \((.*)\)')
    #binnmu_re = re.compile('\+b\d+$')
    dscname_re = re.compile(' ([^ ]*\.dsc)')

    if architecture is None:
        src = True
        tbl = 'source'

        packagesfile = settings.APT_DIR + '/dists/%s/%s/source/Sources.gz' \
                % (release, component)
    else:
        src = False
        tbl = 'package'

        packagesfile = settings.APT_DIR + '/dists/%s/%s/binary-%s/Packages.gz' \
                % (release, component, architecture)

    if not os.path.isfile(packagesfile):
        raise Exception("%s not found" % (packagesfile,))

    #check if an update is necessary
    mtime = os.path.getmtime(packagesfile)
    if last_update and mtime <= last_update + 1 and not running_config['FORCE']: # allow 1s offset for microsecond timestamps
        #if verbose:
        #    print "\t\t%s is uptodate, skipping" % (packagesfile,)
        return

    if verbose:
        print "\t\tRead file %s" % (packagesfile,)

    if not src:
        contents_plain = gzip.open(settings.APT_DIR + '/dists/%s/%s/Contents-%s.gz' \
                % (release, component, architecture))
        contents = buildFileDict(contents_plain)

    sql = "DELETE FROM apt_%slist " % (tbl)
    sql = sql + "WHERE suite_id = %s"
    cursor.execute(sql, (suite_id,))

    content = os.popen("zcat '%s'" % (packagesfile))
    package = apt_pkg.TagFile(content)

    # for each package
    while package.step():
        insert = True
        package_content = {}
        package_content['Package']      = package.section.get('Package')
        package_content['Version']      = package.section.get('Version')
        package_content['Binary']       = package.section.get('Binary')
        package_content['Maintainer']   = package.section.get('Maintainer')
        if package.section.get('Uploaders'):
            package_content['Maintainer'] += ', ' + package.section.get('Uploaders')
        package_content['Architecture'] = package.section.get('Architecture')
        if package.section.get('Description'):
            package_content['Short-Description']  = package.section.get('Description').split('\n')[0]
            description = ''
            list_needs_newline = False
            list_started = False
            for line in package.section.get('Description').split('\n ')[1:]:
                if line == '.':
                    line = ''
                    list_needs_newline = False
                elif line[0:3] == ' * ' or line[0:3] == ' - ':
                    # on seeing a new bullet list, make sure there is a newline before it
                    if list_needs_newline:
                        description += '\n'
                    line = '*' + line[2:]
                    list_needs_newline = False
                    list_started = True
                elif not list_started:
                    list_needs_newline = True
                description += line + '\n'
            package_content['Description'] = markdown.markdown(description.decode("utf-8"), tab_length=1)
        package_content['Homepage']     = package.section.get('Homepage')
        package_content['VCS-Browser']  = package.section.get('VCS-Browser')
        package_content['VCS-Repo']     = package.section.get('VCS-Svn')
        if not package_content['VCS-Repo']:
            package_content['VCS-Repo'] = package.section.get('VCS-Git')
        if not package_content['VCS-Repo']:
            package_content['VCS-Repo'] = package.section.get('VCS-Bzr')
        package_content['Build-Depends'] = package.section.get('Build-Depends')
        package_content['Build-Depends-Indep'] = package.section.get('Build-Depends-Indep')
        if package_content['Build-Depends-Indep']:
            package_content['Build-Depends'] += ", %s" % package_content['Build-Depends-Indep']
        package_content['Depends']      = package.section.get('Depends')
        package_content['Recommends']   = package.section.get('Recommends')
        package_content['Suggests']     = package.section.get('Suggests')
        package_content['Directory']    = package.section.get('Directory')
        package_content['Filename']     = package.section.get('Filename')
        package_content['Size']         = package.section.get('Size')
        if package.section.has_key('Installed-Size'):
            package_content['Installed-Size'] = int(package.section.get('Installed-Size')) * 1024
        package_content['Files']        = package.section.get('Files')

        sourcefield = package.section.get('Source')
        if sourcefield:
            match = source_re.match(sourcefield)
            if match:
                package_content['Source'], package_content['Source-Version'] = \
                        match.group(1), match.group(2)
            else:
                package_content['Source'], package_content['Source-Version'] = \
                        sourcefield, package_content['Version']
        else:
            package_content['Source'], package_content['Source-Version'] = \
                    package_content['Package'], package_content['Version']

        if src:
            match = dscname_re.search(package_content['Files'])
            if not match:
                raise Exception('Files section without .dsc file')
            dscfile = settings.APT_DIR + '/' + package_content['Directory'] + '/' + match.group(1)

            package_content['Copyright'] = None
            try:
                package_content['Copyright'] = subprocess.check_output(
                        ['dscextract', '-f', dscfile, 'debian/copyright'])
            except subprocess.CalledProcessError as e:
                if e.returncode != 1 and not running_config['DISTONLY']:
                    raise

            package_content['Debchangelog'] = None
            try:
                package_content['Debchangelog'] = subprocess.check_output(
                        ['dscextract', '-f', dscfile, 'debian/changelog'])
            except subprocess.CalledProcessError as e:
                if e.returncode != 1 and not running_config['DISTONLY']:
                    raise

            package_content['Changelog'] = None
            try:
                package_content['Changelog'] = None # TODO
            except subprocess.CalledProcessError as e:
                if e.returncode != 1 and not running_config['DISTONLY']:
                    raise

        # check if the package already exists
        sql = "SELECT id FROM apt_%s WHERE " % (tbl)
        if src:
            sql = sql + "(source, srcversion) = (%(Package)s, %(Version)s)"
        else:
            sql = sql + "(package, version, arch_id) = (%(Package)s, %(Version)s, %(Architecture)s)"
        cursor.execute(sql, package_content)
        found = cursor.fetchone()

        if found:
            package_id = found[0]
            if running_config['FORCE']:
                if verbose:
                    print "\t\tPackage %(Package)s already exists, force delete" % package_content

                # delete list entries
                if src:
                    sql = "DELETE FROM apt_sourcelist WHERE source_id = %s"
                else:
                    sql = "DELETE FROM apt_packagelist WHERE package_id = %s"
                cursor.execute(sql, (package_id,))

                # delete files entries
                if src:
                    sql = "DELETE FROM apt_files WHERE source_id = %s"
                    cursor.execute(sql, (package_id,))

                sql = "DELETE FROM apt_%s " % (tbl) + "WHERE id = %s"
                cursor.execute(sql, (package_id,))
                insert = True
            else:
                #if verbose:
                #    print "Package %(Package)s already exists and up to date, continue" % package_content
                insert = False

        if insert:
            if verbose:
                print "\t\tFound new Package %(Package)s (%(Version)s %(Architecture)s), inserting" % package_content

            # isert new package
            sql = "INSERT INTO apt_%s " % (tbl)
            if src:
                sql = sql + "(source, srcversion, \"binary\", architecture, maintainer, homepage, vcs_browser, vcs_repo, build_depends, directory, copyright, debchangelog, changelog) "
                sql = sql + "VALUES (%(Package)s, %(Version)s, %(Binary)s, %(Architecture)s, %(Maintainer)s, %(Homepage)s, %(VCS-Browser)s, %(VCS-Repo)s, %(Build-Depends)s, %(Directory)s, %(Copyright)s, %(Debchangelog)s, %(Changelog)s) "
            else:
                sql = sql + "(package, version, arch_id, source, srcversion, maintainer, short_description, description, homepage, installed_size, filename, depends, recommends, suggests, size) "
                sql = sql + "VALUES (%(Package)s, %(Version)s, %(Architecture)s, %(Source)s, %(Source-Version)s, %(Maintainer)s, %(Short-Description)s, %(Description)s, %(Homepage)s, %(Installed-Size)s, %(Filename)s, %(Depends)s, %(Recommends)s, %(Suggests)s, %(Size)s) "
            sql = sql + "RETURNING id"

            cursor.execute(sql, package_content)
            package_id = cursor.fetchone()[0]

            if src:
                # insert files (dsc, orig.tar.*, ...)
                sql = "INSERT INTO apt_files (files, md5_hash, size, source_id) VALUES (%s, %s, %s, %s)"
                files_lines = package_content['Files'].split('\n')
                for f in files_lines:
                    f = f.strip().split(" ")
                    file_md5_hash = f[0]
                    file_size     = f[1]
                    file_name     = f[2]
                    cursor.execute(sql, (file_name, file_md5_hash, file_size, package_id))
            else:
                # insert contents
                sql = "INSERT INTO apt_packagecontents (package_id, filename) VALUES (%s, %s)"
                for filename in contents[package_content['Package']]:
                    cursor.execute(sql, (package_id, filename))

        sql = "INSERT INTO apt_%slist " % (tbl)
        if src:
            sql = sql + "(suite_id, source_id) "
        else:
            sql = sql + "(suite_id, package_id) "
        sql = sql + "VALUES (%s, %s)"

        cursor.execute(sql, (suite_id, package_id))

    if src:
        sql = "UPDATE apt_srcsuite SET last_update = to_timestamp(%s::int) WHERE (release_id, component_id) = (%s, %s)"
        args_tpl = (mtime, release, component)
    else:
        sql = "UPDATE apt_suite SET last_update = to_timestamp(%s::int) WHERE (release_id, component_id, architecture_id) = (%s, %s, %s)"
        args_tpl = (mtime, release, component, architecture)
    cursor.execute(sql, args_tpl)
    transaction.commit()

if __name__ == '__main__':
    main(sys.argv)
