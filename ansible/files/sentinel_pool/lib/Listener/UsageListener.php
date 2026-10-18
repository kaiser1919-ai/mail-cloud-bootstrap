<?php
declare(strict_types=1);
namespace OCA\SentinelPool\Listener;
use OCP\EventDispatcher\Event;
use OCP\EventDispatcher\IEventListener;
use OCP\AppFramework\Http\Events\BeforeTemplateRenderedEvent;
use OCP\Util;
class UsageListener implements IEventListener {
 public function handle(Event $event): void {
  if (!$event instanceof BeforeTemplateRenderedEvent || !$event->isLoggedIn()) {return;}
  Util::addScript('sentinel_pool', 'usage');
  Util::addStyle('sentinel_pool', 'usage');
 }
}
