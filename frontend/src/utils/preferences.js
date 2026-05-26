export const loadReadNotificationIds = () => {
  try {
    const raw = localStorage.getItem('breathesg_read_notifications');
    return new Set(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set();
  }
};

export const saveReadNotificationIds = (ids) => {
  localStorage.setItem('breathesg_read_notifications', JSON.stringify([...ids]));
};
