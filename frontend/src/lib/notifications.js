// Icons and links for notifications (the icons follow the student dashboard in Figma 05).

const ICONS = {
  course_invitation: 'mail',
  team_invitation: 'users',
  staff_invitation: 'shield',
  join_request_received: 'users',
  enrolment_approved: 'check',
  enrolment_rejected: 'clock',
  resources_published: 'book',
  assignment_published: 'file',
  deadline_extended: 'clock',
  draft_uploaded: 'upload',
  team_member_joined: 'users',
  team_member_left: 'users',
  final_submitted: 'users',
  final_replaced: 'users',
  final_at_deadline: 'clock',
  marks_released: 'star',
  removed_from_course: 'user',
  account_deletion_requested: 'user',
}

export function notificationIcon(eventType) {
  return ICONS[eventType] ?? 'bell'
}

// The backend's links are frontend paths ("/teams/12", "/courses/3#resources"). Keep only
// paths inside this site.
export function notificationLink(link) {
  return link && link.startsWith('/') && !link.startsWith('//') ? link : '/notifications'
}
