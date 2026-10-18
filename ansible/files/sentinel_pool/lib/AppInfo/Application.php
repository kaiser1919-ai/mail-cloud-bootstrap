<?php
declare(strict_types=1);
namespace OCA\SentinelPool\AppInfo;
use OCP\AppFramework\App;
use OCP\AppFramework\Bootstrap\IBootstrap;
use OCP\AppFramework\Bootstrap\IBootContext;
use OCP\AppFramework\Bootstrap\IRegistrationContext;
use OCP\AppFramework\Http\Events\BeforeTemplateRenderedEvent;
use OCA\SentinelPool\Listener\UsageListener;
class Application extends App implements IBootstrap {
 public function __construct(array $urlParams = []) {parent::__construct('sentinel_pool', $urlParams);}
 public function register(IRegistrationContext $context): void {$context->registerEventListener(BeforeTemplateRenderedEvent::class, UsageListener::class);}
 public function boot(IBootContext $context): void {}
}
