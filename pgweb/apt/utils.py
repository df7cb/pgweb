# APT repository interface for the PostgreSQL website
# Authors: Adrian Vondendriesch <adrian.vondendriesch@credativ.de>
#          Christoph Berg <christoph.berg@credativ.de>

from models import Package, PackageList

def build_related_list(rel_list, release):
    result = []
    if rel_list:
        for entry in rel_list.split(","):
            entry = entry.strip()
            l = []
            for subentry in entry.split("|"):
                l.append(build_list_element(subentry, release))
            result.append(l)
    return result

def build_list_element(list_entry, release):
    """Returns tuple (full string, package name, dependency package available in our archive)"""
    list_entry = list_entry.strip()
    s = list_entry.split(" ", 1)
    pkg = s[0]
    dep = ''
    if len(s) > 1:
        dep = s[1]
    pkg_available = len(PackageList.objects.filter(\
            package__package=pkg, \
            suite__release=release))
    return (list_entry, pkg, dep, pkg_available)
