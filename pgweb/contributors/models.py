from django.db import models
from django.contrib.auth.models import User
from pgweb.core.models import Organisation
from pgweb.core.text import ORGANISATION_HINT_TEXT
from pgweb.util.moderation import TwostateModerateModel
from pgweb.util.fields import ImageBinaryField


class ContributorType(models.Model):
    typename = models.CharField(max_length=32, null=False, blank=False)
    sortorder = models.IntegerField(null=False, default=100)
    extrainfo = models.TextField(null=True, blank=True)
    detailed = models.BooleanField(null=False, default=True)
    showemail = models.BooleanField(null=False, default=True)

    purge_urls = ('/community/contributors/', )

    def __str__(self):
        return self.typename

    class Meta:
        ordering = ('sortorder',)


class Contributor(models.Model):
    ctype = models.ForeignKey(ContributorType,
                              on_delete=models.CASCADE,
                              verbose_name='Contributor Type', null=True, blank=True)
    firstname = models.CharField(max_length=100, null=False, blank=False)
    lastname = models.CharField(max_length=100, null=False, blank=False)
    email = models.EmailField(null=True, blank=True)
    company = models.CharField(max_length=100, null=True, blank=True)
    companyurl = models.URLField(max_length=100, null=True, blank=True, verbose_name='Company URL')
    location = models.CharField(max_length=100, null=True, blank=True)
    contribution = models.TextField(null=True, blank=True,
                                    help_text='Describe what you did in the PostgreSQL community')
    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.CASCADE)

    send_notification = True
    purge_urls = ('/community/contributors/', '/community/people/', '/community/badge/')

    def __str__(self):
        return "%s %s" % (self.firstname, self.lastname)

    class Meta:
        ordering = ('lastname', 'firstname',)


class Badge(TwostateModerateModel):
    org = models.ForeignKey(Organisation, null=False, blank=False, verbose_name="Organisation", help_text=ORGANISATION_HINT_TEXT, on_delete=models.CASCADE)
    badge = models.CharField(max_length=32, null=False, blank=False, unique=True, help_text='Title of this badge, e.g. "PGConf.EU 2025 Speaker".')
    description = models.TextField(null=True, blank=True, help_text='What did the people do who contributed here?')
    url = models.URLField(max_length=100, null=True, blank=True, verbose_name='Contribution URL', help_text='URL for this contribution, e.g. the conference homepage. (Leave blank when there is no URL.)')
    imagedata = ImageBinaryField(max_length=1000000, resolution=(150, 150), auto_scale=True, blank=True, null=True, verbose_name="Image", help_text="Square image, will be auto-scaled to 150×150. JPEG or PNG, up to 1 MB. When left blank, the Slony logo will be used.")
    contact = models.CharField(max_length=100, null=True, blank=True, verbose_name='Contact address', help_text='Contact address (email, URL, other) for people who want to be added as badge holder')
    holders = models.ManyToManyField(User, through="Badgeholder", through_fields=("badge", "user"), blank=True)

    sortorder = models.IntegerField(null=True, blank=True, default=100)

    account_edit_suburl = 'badges'
    moderation_fields = ['badge', 'description', 'url']
    send_notification = True
    purge_urls = ('/community/people/', '/community/badge/')

    def verify_submitter(self, user):
        return (len(self.org.managers.filter(pk=user.pk)) == 1)

    def __str__(self):
        return self.badge

    @property
    def title(self):
        return self.badge

    class Meta:
        ordering = ('sortorder', 'badge')

    @classmethod
    def get_formclass(self):
        from pgweb.contributors.forms import BadgeForm
        return BadgeForm


class Badgeholder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)

    date_awarded = models.DateField(auto_now_add=True)
    date_retired = models.DateField(null=True, blank=True)
    awarded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="awarded_by")

    purge_urls = ('/community/people/', '/community/badge/')

    def __str__(self):
        label = f"{self.badge} {self.user.first_name} {self.user.last_name} ({self.user})"
        if self.date_retired:
            label += " (retired)"
        return label

    class Meta:
        ordering = ('badge__sortorder', 'badge', 'user__last_name', 'user__first_name')
        constraints = [
            models.UniqueConstraint(fields=["user", "badge"], name="unique_user_badge")
        ]
