from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Team, Membership

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    first_name = forms.CharField(
        max_length=30, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user


class TeamInviteForm(forms.Form):
    """Form for sending team invitations."""
    
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter email address to invite'
        }),
        help_text="Enter the email address of the person you want to invite to your team."
    )
    
    role = forms.ChoiceField(
        choices=Membership.ROLE_CHOICES,
        initial='Developer',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select the role for the invited team member."
    )
    
    def __init__(self, *args, **kwargs):
        self.team = kwargs.pop('team', None)
        super().__init__(*args, **kwargs)
    
    def clean_email(self):
        email = self.cleaned_data['email']
        
        if not self.team:
            raise forms.ValidationError("Team is required for validation.")
        
        # Check if user is already a team member
        try:
            user = User.objects.get(email=email)
            if Membership.objects.filter(user=user, team=self.team).exists():
                raise forms.ValidationError(f"User with email {email} is already a member of this team.")
        except User.DoesNotExist:
            # User doesn't exist yet, which is fine for invitations
            pass
        
        # Check for existing pending invitation
        from .models import TeamInvitation
        existing_invitation = TeamInvitation.objects.filter(
            team=self.team,
            email=email,
            status='pending'
        ).first()
        
        if existing_invitation and not existing_invitation.is_expired():
            raise forms.ValidationError(f"A pending invitation already exists for {email}.")
        
        return email