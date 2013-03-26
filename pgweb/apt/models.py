# APT repository interface for the PostgreSQL website
# Authors: Adrian Vondendriesch <adrian.vondendriesch@credativ.de>
#          Christoph Berg <christoph.berg@credativ.de>

from django.db import models
from datetime import datetime

class Vendor(models.Model):
    vendor       = models.TextField(null=False, primary_key=True)

    def __unicode(self):
        return vendor;

class Release(models.Model):
    vendor       = models.ForeignKey(Vendor)
    release      = models.TextField(null=False, primary_key=True)
    relversion   = models.TextField()
    active       = models.BooleanField(null=False, default=True)

    def __unicode(self):
        return release;

class Architecture(models.Model):
    architecture = models.TextField(null=False, primary_key=True)

    def __unicode(self):
        return architecture;

class Component(models.Model):
    component    = models.TextField(null=False, primary_key=True)

    def __unicode__(self):
        return self.component

class Suite(models.Model):
    release      = models.ForeignKey(Release)
    component    = models.ForeignKey(Component)
    architecture = models.ForeignKey(Architecture)
    last_update  = models.DateTimeField(null=True)
    active       = models.BooleanField(null=False, default=True)

    class Meta:
        unique_together = (("release", "component", "architecture"),)

class Srcsuite(models.Model):
    release      = models.ForeignKey(Release)
    component    = models.ForeignKey(Component)
    last_update  = models.DateTimeField(null=True)
    active       = models.BooleanField(null=False, default=True)

    class Meta:
        unique_together = (("release", "component"),)

class Package(models.Model):
    package      = models.TextField(null=False)
    version      = models.TextField(null=False)
    arch         = models.ForeignKey(Architecture)
    source       = models.TextField(null=False)
    srcversion   = models.TextField(null=False)
    maintainer   = models.TextField(null=False)
    short_description  = models.TextField(null=False)
    description  = models.TextField(null=True)
    homepage     = models.TextField(null=True)
    installed_size = models.IntegerField(null=False)
    filename     = models.TextField(null=False)
    depends      = models.TextField(null=True)
    recommends   = models.TextField(null=True)
    suggests     = models.TextField(null=True)
    size         = models.IntegerField(null=False)

    class Meta:
        unique_together = (("package", "version", "arch"))

    def __unicode__(self):
        return self.package

class PackageList(models.Model):
    suite        = models.ForeignKey(Suite)
    package      = models.ForeignKey(Package)

class PackageContents(models.Model):
    package      = models.ForeignKey(Package)
    filename     = models.TextField(null=False)

class Source(models.Model):
    source       = models.TextField(null=False)
    srcversion   = models.TextField(null=False)
    binary       = models.TextField(null=False)
    architecture = models.TextField(null=False)
    maintainer   = models.TextField(null=False)
    homepage     = models.TextField(null=True)
    short_description  = models.TextField(null=True)
    description  = models.TextField(null=True)
    vcs_browser  = models.TextField(null=True)
    vcs_repo     = models.TextField(null=True)
    build_depends = models.TextField(null=True)
    directory    = models.TextField(null=True)
    copyright    = models.TextField(null=True)
    debchangelog = models.TextField(null=True)
    changelog    = models.TextField(null=True)

    class Meta:
        unique_together = (("source", "srcversion"))

    def __unicode__(self):
        return self.source

class SourceList(models.Model):
    suite        = models.ForeignKey(Srcsuite)
    source       = models.ForeignKey(Source)

# because file is a common identifier I use files as classname
class Files(models.Model):
    files        = models.TextField(null=False)
    md5_hash     = models.TextField(null=False)
    size         = models.IntegerField(null=False)
    source       = models.ForeignKey(Source)

    unitque_together = (("files", "md5_hash", "size"),)

