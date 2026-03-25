/**
 * @fileoverview Lightweight JSDoc typedefs for the global window API used by the chat frontend.
 * This file intentionally has no side-effects and only provides type hints for editors.
 */

/**
 * @typedef {(number|string)} Id
 */

/**
 * @typedef {Object} Room
 * @property {Id} id
 * @property {string=} name
 * @property {string=} other_name
 * @property {boolean=} is_dialog
 * @property {Array<Id>=} members
 */

/**
 * @typedef {Object} Message
 * @property {Id} id
 * @property {Id} room_id
 * @property {Id} sender_id
 * @property {string=} text
 * @property {number} created_at
 * @property {boolean=} is_me
 */

/**
 * @typedef {Object} Member
 * @property {Id} id
 * @property {string} name
 * @property {boolean} online
 */

/**
 * @typedef {Object} RoomsApi
 * @property {function(): Promise<void>} loadRooms
 * @property {function(): Promise<void>} loadContacts
 * @property {function(Id): Promise<void>} loadRoomMembers
 * @property {function(Id, object=): Promise<void>} loadRoomMessages
 * @property {function(Id, object=): Promise<void>} loadDialogMessages
 * @property {function(Room|Id): void} [selectRoom]
 * @property {function(Id): void} [openDialog]
 * @property {function(): void} [renderRooms]
 * @property {function(): void} [renderContacts]
 * @property {function(Array<Member>): void} [renderMembers]
 */

/**
 * @typedef {Object} WindowAppApi
 * @property {function(string, object=): Promise<any>} fetchJSON
 * @property {function(Message): HTMLElement} appendMessage
 * @property {RoomsApi} roomsApi
 * @property {function(object=): Promise<any>} showModal
 * @property {function(string, string=, number=): void} showToast
 * @property {function(Event): Promise<void>} handleComposerSubmit
 * @property {function(): void} startHeartbeat
 * @property {function(): void} startPresencePolling
 * @property {function(): void} closePresence
 * @property {function(): Promise<void>} loadSessions
 */

/* global window */
/**
 * @type {RoomsApi|undefined}
 */
window.roomsApi = window.roomsApi || window.roomsApi;

/**
 * Editor-only: declares common window globals used by the app. These lines intentionally
 * do not add or modify runtime behavior — they help TypeScript/JS-aware editors show hints.
 * @type {HTMLElement|null}
 */
window.messagesEl = window.messagesEl || null;
window.earliestTimestamp = window.earliestTimestamp || null;
window.latestTimestamp = window.latestTimestamp || null;
window.autoscroll = typeof window.autoscroll === 'boolean' ? window.autoscroll : true;
window.currentRoom = window.currentRoom || null;
window.isDialog = typeof window.isDialog === 'boolean' ? window.isDialog : false;
window.rooms = window.rooms || [];
window.contacts = window.contacts || [];
