-- 0005_unique_boards_in_progress: a board is in progress at most once, so picking it up by its
-- MAC or by its QR ID always finds exactly one row (and a QR sticker cannot be on two boards
-- that are both still on the line).

-- Databases that already hold such duplicates keep the newest row and abandon the others.
UPDATE devices SET status = 'abandoned', finished_at = started_at, next_op = NULL
WHERE status = 'in_progress' AND id NOT IN (
    SELECT MAX(id) FROM devices WHERE status = 'in_progress' GROUP BY mac_address);
UPDATE devices SET status = 'abandoned', finished_at = started_at, next_op = NULL
WHERE status = 'in_progress' AND device_id IS NOT NULL AND id NOT IN (
    SELECT MAX(id) FROM devices
    WHERE status = 'in_progress' AND device_id IS NOT NULL GROUP BY device_id);

CREATE UNIQUE INDEX ux_devices_mac_in_progress ON devices (mac_address)
    WHERE status = 'in_progress';
CREATE UNIQUE INDEX ux_devices_qr_in_progress ON devices (device_id)
    WHERE status = 'in_progress' AND device_id IS NOT NULL;
